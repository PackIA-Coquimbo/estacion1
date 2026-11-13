"""Regression checks for multiple fruit captures on one camera."""

import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from src.main import assess, detect_oranges, save_capture
from src.tracker import FruitTracker


def make_frame(shift=0):
    frame = np.full((720, 1280, 3), 225, dtype=np.uint8)
    for center_x in (470 + shift, 790 + shift):
        cv2.circle(frame, (center_x, 530), 100, (0, 135, 235), -1)
        # Visible texture gives the focus check a realistic signal.
        rng = np.random.default_rng(center_x)
        ys, xs = np.ogrid[:720, :1280]
        inside = (xs - center_x) ** 2 + (ys - 530) ** 2 < 95 ** 2
        noise = rng.integers(-12, 13, size=(int(inside.sum()), 3))
        frame[inside] = np.clip(frame[inside].astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return frame


class MultiFruitTest(unittest.TestCase):
    def test_two_fruits_keep_ids_and_make_separate_crops(self):
        frame = make_frame()
        boxes = detect_oranges(frame)
        self.assertEqual(len(boxes), 2)
        tracker = FruitTracker()
        first = tracker.update(boxes, 0.0)
        second = tracker.update(detect_oranges(make_frame(8)), 0.5)
        self.assertEqual({track.track_id for track, _ in first},
                         {track.track_id for track, _ in second})

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for track, box in second:
                good, score, _ = assess(frame, box)
                self.assertTrue(good)
                save_capture(frame, box, score, root / "captures", root / "outbox", "cam_izq", track.track_id)
            records = [json.loads(path.read_text(encoding="utf-8"))
                       for path in (root / "outbox").glob("*.json")]
            self.assertEqual(len(records), 2)
            self.assertEqual({record["camera_track_id"] for record in records}, {1, 2})
            self.assertTrue(all(record["camera_id"] == "cam_izq" for record in records))
            self.assertTrue(all((record["image_width"], record["image_height"]) == (480, 640)
                                for record in records))
            for record in records:
                photo = root / "outbox" / record["photo"]
                with Image.open(photo) as saved:
                    self.assertEqual(saved.size, (480, 640))
                self.assertEqual(record["output_framing"], "pad")


if __name__ == "__main__":
    unittest.main()
