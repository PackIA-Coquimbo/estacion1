"""Burst capture keeps distinct synchronized views under one fruit ID."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

from src.burst import AutoBurst, BurstCollector
from src.config import CaptureConfig
from src.detector import evaluate_position
from src.image_quality import evaluate_quality
from src.paired_capture import camera_loop, process_burst


class BurstTests(unittest.TestCase):
    def setUp(self):
        self.config = CaptureConfig()
        self.empty = Image.new("RGB", (1280, 720), (100, 100, 100))
        rng = np.random.default_rng(42)
        base = np.full((720, 1280, 3), 100, dtype=np.uint8)
        yy, xx = np.ogrid[:720, :1280]
        fruit = (xx - 640) ** 2 + (yy - 360) ** 2 <= 140 ** 2
        texture = rng.integers(40, 220, size=(720, 1280), dtype=np.uint8)
        base[fruit] = np.repeat(texture[fruit, None], 3, axis=1)
        self.first = Image.fromarray(base)
        self.rotated = self.first.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        self.cameras = ("camara_0", "camara_1")
        self.configs = {camera: self.config for camera in self.cameras}
        self.references = {camera: self.empty for camera in self.cameras}

    def view(self, image):
        images = {camera: image for camera in self.cameras}
        results = {}
        for camera in self.cameras:
            position = evaluate_position(image, self.empty, self.config)
            quality = evaluate_quality(image, self.config, position.subject_bounds)
            results[camera] = quality, position
        return images, results

    def test_interval_and_visual_change_filter(self):
        collector = BurstCollector(self.cameras, max_pairs=2, interval_seconds=0.35,
                                   min_change=1.5)
        first, results = self.view(self.first)
        rotated, rotated_results = self.view(self.rotated)
        self.assertTrue(collector.offer(first, results, 0.0))
        self.assertFalse(collector.offer(rotated, rotated_results, 0.1))
        self.assertFalse(collector.offer(first, results, 0.5))
        self.assertTrue(collector.offer(rotated, rotated_results, 0.5))
        self.assertTrue(collector.full)
        self.assertFalse(collector.offer(first, results, 1.0))
        self.assertEqual(len(collector.pairs), 2)

    def test_each_camera_keeps_good_views_when_other_camera_fails(self):
        collector=BurstCollector(self.cameras,max_pairs=1,interval_seconds=.35,require_all=False)
        images,good=self.view(self.first)
        _,bad=self.view(self.empty)
        self.assertTrue(collector.offer(images,{'camara_0':good['camara_0'],'camara_1':bad['camara_1']},0))
        self.assertEqual(set(collector.pairs[0]),{'camara_0'})
        self.assertFalse(collector.full)
        self.assertTrue(collector.offer(images,{'camara_0':bad['camara_0'],'camara_1':good['camara_1']},.1))
        self.assertEqual(set(collector.pairs[1]),{'camara_1'})
        self.assertTrue(collector.full)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with redirect_stdout(StringIO()):
                accepted=process_burst(collector.pairs,'L1','F1',self.configs,
                    root/'out',root/'bad',self.references)
            self.assertEqual(accepted,2)
            records=[json.loads(p.read_text(encoding='utf-8')) for p in (root/'out').rglob('*.json')]
            self.assertEqual({r['id_fruta'] for r in records},{'F1'})
            self.assertTrue(all(r['vistas_incompletas'] for r in records))
            self.assertTrue(all(len(r['vistas'])==1 for r in records))

    def test_collection_mode_keeps_physical_fruit_ids_until_n(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            args=SimpleNamespace(camera=0,camera_2=1,capture_width=1280,capture_height=720,
                gap_frames=2,burst_count=4,burst_interval_ms=1,burst_min_change=0,
                auto=True,collect_training=True,lot='L1',fruit='F1',output=root/'out',
                evidence=root/'bad',training_dir=root/'raw',output_framing='crop')
            class FakeCamera:
                def read(inner): return True,cv2.cvtColor(np.asarray(self.first),cv2.COLOR_RGB2BGR)
                def get(inner,property_id): return 1280 if property_id==cv2.CAP_PROP_FRAME_WIDTH else 720
                def release(inner): pass
            keys=iter((ord('t'),ord('n'),ord('t'),ord('q')))
            with patch('src.paired_capture.open_camera',side_effect=lambda *a:FakeCamera()), \
                 patch('cv2.imshow'),patch('cv2.waitKey',side_effect=lambda _:next(keys)), \
                 patch('cv2.destroyAllWindows'),redirect_stdout(StringIO()):
                camera_loop(args,self.configs,{})
            records=[json.loads(p.read_text(encoding='utf-8')) for p in (root/'raw').glob('*.json')]
            self.assertEqual(len(records),4)
            self.assertEqual({r['fruit_group'] for r in records},{'L1__F1','L1__F2'})
            self.assertFalse((root/'out').exists())

    def test_auto_burst_waits_for_empty_gap(self):
        automatic = AutoBurst(self.cameras, gap_frames=2, max_pairs=2,
                              interval_seconds=0.35, min_change=1.5)
        first, first_results = self.view(self.first)
        rotated, rotated_results = self.view(self.rotated)
        empty, empty_results = self.view(self.empty)
        self.assertIsNone(automatic.observe(first, first_results, 0.0))
        self.assertIsNone(automatic.observe(rotated, rotated_results, 0.5))
        self.assertIsNone(automatic.observe(empty, empty_results, 0.6))
        selected = automatic.observe(empty, empty_results, 0.7)
        self.assertEqual(len(selected), 2)
        self.assertFalse(automatic.active)
        self.assertIsNone(automatic.observe(first, first_results, 1.0))
        self.assertTrue(automatic.active)

    def test_saved_pairs_share_fruit_and_burst_id(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            pairs = [self.view(self.first)[0], self.view(self.rotated)[0]]
            with redirect_stdout(StringIO()):
                accepted = process_burst(pairs, "Lote_001", "Fruta_001",
                                         self.configs, root / "out", root / "evidence",
                                         self.references)
            self.assertEqual(accepted, 2)
            manifests = [json.loads(path.read_text(encoding="utf-8"))
                         for path in sorted((root / "out").rglob("*.json"))]
            self.assertEqual(len(manifests), 2)
            self.assertEqual([item["indice_rafaga"] for item in manifests], [1, 2])
            self.assertEqual({item["total_rafaga"] for item in manifests}, {2})
            self.assertEqual({item["id_fruta"] for item in manifests}, {"Fruta_001"})
            self.assertEqual(len({item["id_rafaga"] for item in manifests}), 1)
            self.assertEqual(len(list((root / "out").rglob("*.jpg"))), 4)

    def test_manual_r_key_saves_one_burst_for_one_fruit(self):
        class FakeCamera:
            def __init__(self, frames):
                self.frames = iter(frames)

            def read(self):
                return True, next(self.frames)

            def get(self, property_id):
                return 1280 if property_id == cv2.CAP_PROP_FRAME_WIDTH else 720

            def release(self):
                pass

        sequence = [self.empty, self.first, self.rotated, self.rotated, self.empty]
        frames = [cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR) for image in sequence]
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temporary:
            root = Path(temporary)
            args = SimpleNamespace(camera=0, camera_2=1, capture_width=1280,
                                   capture_height=720, gap_frames=2, burst_count=4,
                                   burst_interval_ms=1, burst_min_change=0,
                                   auto=False, lot="Lote_001", fruit="Fruta_001",
                                   output=root / "out", evidence=root / "evidence",
                                   output_framing="crop")
            keys = iter((ord("b"), ord("r"), 0, ord("r"), ord("q")))
            with patch("src.paired_capture.open_camera", side_effect=lambda *a: FakeCamera(frames)), \
                 patch("cv2.imshow"), patch("cv2.waitKey", side_effect=lambda _: next(keys)), \
                 patch("cv2.destroyAllWindows"), redirect_stdout(StringIO()):
                status = camera_loop(args, self.configs, {})
            self.assertEqual(status, 0)
            manifests = [json.loads(path.read_text(encoding="utf-8"))
                         for path in (root / "out").rglob("*.json")]
            self.assertEqual(len(manifests), 2)
            self.assertEqual({item["id_fruta"] for item in manifests}, {"Fruta_001"})
            self.assertEqual(args.fruit, "Fruta_002")


if __name__ == "__main__":
    unittest.main()
