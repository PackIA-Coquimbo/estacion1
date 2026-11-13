"""Selecciona el mejor fotograma de cada cámara durante el paso de una fruta."""

from PIL import Image

from .detector import PositionResult
from .image_quality import QualityResult


class PassageSelector:
    def __init__(self, cameras: tuple[str, ...], gap_frames: int = 3):
        if not cameras or gap_frames < 1:
            raise ValueError("Se requiere al menos una cámara y gap_frames >= 1")
        self.cameras = cameras
        self.gap_frames = gap_frames
        self.active = False
        self.absent = 0
        self.best: dict[str, tuple[float, Image.Image]] = {}

    def observe(self, frames: dict[str, Image.Image],
                results: dict[str, tuple[QualityResult, PositionResult]]
                ) -> dict[str, Image.Image] | None:
        primary_present = results[self.cameras[0]][1].correct
        if primary_present:
            self.active = True
            self.absent = 0
        elif self.active:
            self.absent += 1
        if not self.active:
            return None

        for camera in self.cameras:
            quality, position = results[camera]
            metrics = quality.metrics
            score = (1_000_000 * position.correct + 100_000 * quality.accepted
                     + float(metrics["nitidez_laplaciano"])
                     + 5 * float(metrics["contraste"])
                     - abs(float(metrics["brillo"]) - 130))
            if camera not in self.best or score > self.best[camera][0]:
                self.best[camera] = (score, frames[camera].copy())

        if self.absent < self.gap_frames:
            return None
        selected = {camera: self.best[camera][1] for camera in self.cameras}
        self.active = False
        self.absent = 0
        self.best.clear()
        return selected
