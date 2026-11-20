import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from src.windows_camera_launcher import discover_cameras, select_cameras


class CameraLauncherTests(unittest.TestCase):
    def test_selects_two_detected_cameras_without_prompt(self):
        with patch("builtins.input") as prompt:
            self.assertEqual(
                select_cameras([(0, "Cámara A"), (2, "Cámara B")]),
                (0, 2),
            )
        prompt.assert_not_called()

    def test_prompts_for_distinct_indices_when_more_than_two_are_detected(self):
        output = io.StringIO()
        with redirect_stdout(output), patch("builtins.input", side_effect=["x", "2", "2", "3"]):
            self.assertEqual(
                select_cameras([(0, "Cámara A"), (2, "Cámara B"), (3, "Cámara C")]),
                (2, 3),
            )
        self.assertIn("2: Cámara B", output.getvalue())

    def test_requires_at_least_two_detected_cameras(self):
        with self.assertRaisesRegex(RuntimeError, "se necesitan al menos dos"):
            select_cameras([(0, "Cámara A")])

    def test_discovery_keeps_only_cameras_that_deliver_a_frame(self):
        class Capture:
            def __init__(self, delivers_frame):
                self.delivers_frame = delivers_frame
                self.released = False

            def read(self):
                return (True, object()) if self.delivers_frame else (False, None)

            def release(self):
                self.released = True

        opened = {}
        names = ["Cámara A", "Cámara B", "Cámara C"]

        def open_camera(_backend, index, _width, _height):
            if index not in (0, 2):
                raise RuntimeError("No camera")
            opened[index] = Capture(index == 2)
            return opened[index]

        with patch("src.windows_camera_launcher.camera_device_names", return_value=names):
            with patch("src.windows_camera_launcher.open_camera", side_effect=open_camera):
                self.assertEqual(discover_cameras(), [(2, "Cámara C")])
        self.assertTrue(opened[0].released)
        self.assertTrue(opened[2].released)


if __name__ == "__main__":
    unittest.main()
