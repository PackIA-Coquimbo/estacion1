import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageFilter

from src.config import CaptureConfig
from src.detector import evaluate_position
from src.image_quality import evaluate_quality
from src.paired_capture import process_capture
from src.output_image import prepare_output
from src.passage import PassageSelector


def fruit_scene():
    rng = np.random.default_rng(42)
    base = np.full((720, 1280, 3), 100, dtype=np.uint8)
    yy, xx = np.ogrid[:720, :1280]
    fruit = (xx - 640) ** 2 + (yy - 360) ** 2 <= 140 ** 2
    texture = rng.integers(40, 220, size=(720, 1280), dtype=np.uint8)
    base[fruit] = np.repeat(texture[fruit, None], 3, axis=1)
    return Image.fromarray(base), Image.new("RGB", (1280, 720), (100, 100, 100))


class StationOneTests(unittest.TestCase):
    def setUp(self):
        self.config = CaptureConfig()
        self.good, self.empty = fruit_scene()

    def test_quality_and_position(self):
        position = evaluate_position(self.good, self.empty, self.config)
        self.assertTrue(position.correct)
        self.assertGreater(position.metrics["ancho_fruta_px"], 100)
        self.assertTrue(evaluate_quality(self.good, self.config, position.subject_bounds).accepted)
        blurred = self.good.filter(ImageFilter.GaussianBlur(8))
        self.assertIn(
            "imagen_borrosa",
            evaluate_quality(blurred, self.config, position.subject_bounds).reasons
        )
        self.assertFalse(evaluate_position(self.empty, self.empty, self.config).correct)
        self.assertFalse(evaluate_position(self.good, None, self.config).correct)

    def test_one_and_two_camera_delivery(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            output, evidence = root / "e2", root / "evidence"
            configs = {"camara_0": self.config, "camara_1": self.config}
            refs = {"camara_0": self.empty, "camara_1": self.empty}
            images = {"camara_0": self.good, "camara_1": self.good.transpose(Image.Transpose.FLIP_LEFT_RIGHT)}
            metadata, photos, manifest = process_capture(
                images, "Lote_001", "Fruta_001", configs, output, evidence, refs
            )
            self.assertEqual(metadata["estado_captura"], "aceptada")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["id_fruta"], "Fruta_001")
            self.assertEqual(len(payload["vistas"]), 2)
            for view in payload["vistas"]:
                photo = photos[view["camara"]]
                self.assertEqual(view["sha256"], hashlib.sha256(photo.read_bytes()).hexdigest())
                self.assertEqual(view["imagen"], photo.name)
                with Image.open(photo) as saved:
                    self.assertEqual(saved.size, (480, 640))
                self.assertEqual(view["resolucion_origen_px"], [1280, 720])
                self.assertEqual(view["resolucion_guardada_px"], [480, 640])
                self.assertEqual(view["encuadre_salida"], "crop")
                self.assertIsNotNone(view["recorte_origen_xyxy"])
            rejected, _, _ = process_capture(
                {"camara_0": self.good, "camara_1": self.empty},
                "Lote_001", "Fruta_002", configs, output, evidence, refs
            )
            self.assertEqual(rejected["estado_captura"], "repetir_captura")
            self.assertEqual(len(list(output.rglob("*.json"))), 1)
            self.assertEqual(rejected["vistas"][0]["encuadre_salida"], "original_evidencia")
            single, single_photos, _ = process_capture(
                {"camara_0": self.good}, "Lote_001", "Fruta_003",
                {"camara_0": self.config}, output, evidence, {"camara_0": self.empty}
            )
            self.assertEqual(single["estado_captura"], "aceptada")
            self.assertEqual(len(single_photos), 1)

    def test_output_framing_keeps_fruit_visible_without_stretching(self):
        image = Image.new("RGB", (1280, 720), (80, 80, 80))
        image.paste((255, 110, 0), (930, 290, 1050, 410))
        prepared, mode, box = prepare_output(
            image, (930, 290, 1050, 410), self.config.roi
        )
        self.assertEqual((prepared.size, mode), ((480, 640), "crop"))
        self.assertLessEqual(box[0], 930)
        self.assertGreaterEqual(box[2], 1050)
        self.assertEqual(round((box[2] - box[0]) / (box[3] - box[1]), 3), 0.75)
        self.assertEqual(prepared.getpixel((240, 320)), (255, 110, 0))

        padded, mode, box = prepare_output(
            image, (930, 290, 1050, 410), self.config.roi, "pad"
        )
        self.assertEqual((padded.size, mode, box), ((480, 640), "pad", None))
        self.assertEqual(padded.getpixel((240, 10)), (32, 32, 32))

        oversized, mode, box = prepare_output(
            image, (100, 100, 1180, 620), self.config.roi
        )
        self.assertEqual((oversized.size, mode, box), ((480, 640), "pad", None))

    def test_passage_selects_best_and_rearms_after_gap(self):
        selector = PassageSelector(("camara_0", "camara_1"), gap_frames=2)
        good_position = evaluate_position(self.good, self.empty, self.config)
        absent_position = evaluate_position(self.empty, self.empty, self.config)
        good_quality = evaluate_quality(self.good, self.config, good_position.subject_bounds)
        bad_quality = evaluate_quality(self.empty, self.config)
        frames = {"camara_0": self.good, "camara_1": self.good}
        present = {camera: (good_quality, good_position) for camera in frames}
        absent = {camera: (bad_quality, absent_position) for camera in frames}
        self.assertIsNone(selector.observe(frames, present))
        self.assertIsNone(selector.observe({"camara_0": self.empty, "camara_1": self.empty}, absent))
        selected = selector.observe({"camara_0": self.empty, "camara_1": self.empty}, absent)
        self.assertEqual(set(selected), set(frames))
        self.assertIsNone(selector.observe(frames, present))
        self.assertTrue(selector.active)


if __name__ == "__main__":
    unittest.main()
