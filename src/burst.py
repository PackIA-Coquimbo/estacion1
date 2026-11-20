"""Collect synchronized, useful views of one fruit from all cameras."""

import numpy as np
from PIL import Image, ImageFilter

from .detector import PositionResult
from .image_quality import QualityResult


class BurstCollector:
    def __init__(self, cameras: tuple[str, ...], max_pairs: int = 12,
                 interval_seconds: float = 0.35, min_change: float = 0.0,
                 require_all: bool = True):
        if not cameras or not 1 <= max_pairs <= 32 or interval_seconds <= 0 or min_change < 0:
            raise ValueError("Configuración de ráfaga no válida")
        self.cameras = cameras
        self.max_pairs = max_pairs
        self.interval_seconds = interval_seconds
        self.min_change = min_change
        self.require_all=require_all
        self.camera_counts={camera:0 for camera in cameras}
        self.camera_times={}
        self.pairs: list[dict[str, Image.Image]] = []
        self.last_at: float | None = None
        self.last_signatures: dict[str, np.ndarray] = {}

    @property
    def full(self) -> bool:
        if not self.require_all:
            return all(count>=self.max_pairs for count in self.camera_counts.values())
        return len(self.pairs) >= self.max_pairs

    @staticmethod
    def _signature(image: Image.Image, bounds: tuple[int, int, int, int]) -> np.ndarray:
        subject = image.crop(bounds).convert("L").resize((48, 48))
        return np.asarray(subject.filter(ImageFilter.GaussianBlur(1)), dtype=np.float32)

    def offer(self, images: dict[str, Image.Image],
              results: dict[str, tuple[QualityResult, PositionResult]],
              now: float) -> bool:
        """Store a simultaneous pair if it is valid and visibly different."""
        if not self.require_all:
            selected={}
            for camera in self.cameras:
                quality,position=results[camera]
                if (self.camera_counts[camera]>=self.max_pairs or not quality.accepted
                        or not position.correct or position.subject_bounds is None
                        or now-self.camera_times.get(camera,float('-inf'))<self.interval_seconds):
                    continue
                signature=self._signature(images[camera],position.subject_bounds)
                if (camera in self.last_signatures and self.min_change
                        and float(np.mean(np.abs(signature-self.last_signatures[camera])))<self.min_change):
                    continue
                selected[camera]=images[camera].copy()
                self.last_signatures[camera]=signature
                self.camera_times[camera]=now
                self.camera_counts[camera]+=1
            if selected:
                self.pairs.append(selected)
            return bool(selected)
        if self.full or (self.last_at is not None
                         and now - self.last_at < self.interval_seconds):
            return False
        if any(not results[camera][0].accepted or not results[camera][1].correct
               or results[camera][1].subject_bounds is None for camera in self.cameras):
            return False
        signatures = {
            camera: self._signature(images[camera], results[camera][1].subject_bounds)
            for camera in self.cameras
        }
        if self.last_signatures and self.min_change:
            change = max(float(np.mean(np.abs(signatures[camera] - self.last_signatures[camera])))
                         for camera in self.cameras)
            if change < self.min_change:
                return False
        self.pairs.append({camera: images[camera].copy() for camera in self.cameras})
        self.last_signatures = signatures
        self.last_at = now
        return True


class AutoBurst:
    """Keep one fruit active until the capture zone is empty for a short gap."""

    def __init__(self, cameras: tuple[str, ...], gap_frames: int, max_pairs: int,
                 interval_seconds: float, min_change: float, require_all: bool = True):
        if gap_frames < 1:
            raise ValueError("gap_frames debe ser al menos 1")
        self.cameras = cameras
        self.gap_frames = gap_frames
        self.max_pairs = max_pairs
        self.interval_seconds = interval_seconds
        self.min_change = min_change
        self.require_all=require_all
        self.active = False
        self.absent = 0
        self.collector = self._new_collector()

    def _new_collector(self) -> BurstCollector:
        return BurstCollector(self.cameras, self.max_pairs,
                              self.interval_seconds, self.min_change,self.require_all)

    def observe(self, images: dict[str, Image.Image],
                results: dict[str, tuple[QualityResult, PositionResult]],
                now: float) -> list[dict[str, Image.Image]] | None:
        present = any(results[camera][1].subject_bounds is not None for camera in self.cameras)
        if present:
            self.active = True
            self.absent = 0
            self.collector.offer(images, results, now)
        elif self.active:
            self.absent += 1
        if not self.active or self.absent < self.gap_frames:
            return None
        pairs = self.collector.pairs
        self.active = False
        self.absent = 0
        self.collector = self._new_collector()
        return pairs
