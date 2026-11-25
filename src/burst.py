"""Collect synchronized, useful views of one fruit from all cameras."""

from dataclasses import dataclass
import numpy as np
from PIL import Image, ImageFilter

from .detector import PositionResult
from .image_quality import QualityResult


@dataclass(frozen=True)
class BurstSample:
    camera: str
    image: Image.Image
    quality: QualityResult
    position: PositionResult
    score: float
    captured_at: float


def quality_score(quality: QualityResult, position: PositionResult) -> float:
    """Rank higher sharpness, YOLO confidence, contrast, and optimal brightness."""
    metrics = quality.metrics
    sharpness = float(metrics.get("nitidez_laplaciano", 0.0))
    contrast = float(metrics.get("contraste", 0.0))
    brightness = float(metrics.get("brillo", 130.0))
    clipped = float(metrics.get("fraccion_saturada", 0.0))
    confidence = float(position.metrics.get("confianza_yolo", 0.0))
    return (
        sharpness
        + 2.0 * contrast
        + 80.0 * confidence
        - 0.5 * abs(brightness - 130.0)
        - 200.0 * clipped
    )


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
        self.require_all = require_all
        self.camera_counts = {camera: 0 for camera in cameras}
        self.camera_times = {}
        self.camera_samples: dict[str, list[BurstSample]] = {camera: [] for camera in cameras}
        self.pairs: list[dict[str, Image.Image]] = []
        self.last_at: float | None = None
        self.last_signatures: dict[str, np.ndarray] = {}

    @property
    def full(self) -> bool:
        if not self.require_all:
            return all(count >= self.max_pairs for count in self.camera_counts.values())
        return len(self.pairs) >= self.max_pairs

    @staticmethod
    def _signature(image: Image.Image, bounds: tuple[int, int, int, int]) -> np.ndarray:
        subject = image.crop(bounds).convert("L").resize((48, 48))
        return np.asarray(subject.filter(ImageFilter.GaussianBlur(1)), dtype=np.float32)

    def _record_sample(self, camera: str, image_copy: Image.Image,
                       quality: QualityResult, position: PositionResult, now: float) -> None:
        self.camera_samples[camera].append(
            BurstSample(
                camera=camera,
                image=image_copy,
                quality=quality,
                position=position,
                score=quality_score(quality, position),
                captured_at=now,
            )
        )

    def offer(self, images: dict[str, Image.Image],
              results: dict[str, tuple[QualityResult, PositionResult]],
              now: float) -> bool:
        """Store a simultaneous pair if it is valid and visibly different."""
        if not self.require_all:
            selected = {}
            for camera in self.cameras:
                quality, position = results[camera]
                if (self.camera_counts[camera] >= self.max_pairs or not quality.accepted
                        or not position.correct or position.subject_bounds is None
                        or now - self.camera_times.get(camera, float('-inf')) < self.interval_seconds):
                    continue
                signature = self._signature(images[camera], position.subject_bounds)
                if (camera in self.last_signatures and self.min_change
                        and float(np.mean(np.abs(signature - self.last_signatures[camera]))) < self.min_change):
                    continue
                image_copy = images[camera].copy()
                selected[camera] = image_copy
                self._record_sample(camera, image_copy, quality, position, now)
                self.last_signatures[camera] = signature
                self.camera_times[camera] = now
                self.camera_counts[camera] += 1
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
        copied = {}
        for camera in self.cameras:
            quality, position = results[camera]
            image_copy = images[camera].copy()
            copied[camera] = image_copy
            self._record_sample(camera, image_copy, quality, position, now)
            self.camera_counts[camera] += 1
        self.pairs.append(copied)
        self.last_signatures = signatures
        self.last_at = now
        return True

    def select_best(self, keep_per_camera: int = 1,
                    min_sharpness_ratio: float = 0.0) -> tuple[list[dict[str, Image.Image]], list[dict]]:
        """Keep up to keep_per_camera highest-scoring views per camera and return rejected ones."""
        if not any(self.camera_samples.values()):
            return list(self.pairs), []
        effective_keep = self.max_pairs if keep_per_camera <= 0 else keep_per_camera
        kept_by_camera: dict[str, list[BurstSample]] = {}
        rejected: list[dict] = []
        for camera in self.cameras:
            samples = sorted(
                self.camera_samples[camera],
                key=lambda sample: (-sample.score, sample.captured_at),
            )
            best_sharpness = max(
                (float(s.quality.metrics.get("nitidez_laplaciano", 0.0)) for s in samples),
                default=0.0,
            )
            kept: list[BurstSample] = []
            for sample in samples:
                sharpness = float(sample.quality.metrics.get("nitidez_laplaciano", 0.0))
                if not kept:
                    kept.append(sample)
                    continue
                if len(kept) >= effective_keep:
                    reason = "fuera_de_top_calidad"
                elif (min_sharpness_ratio > 0 and best_sharpness > 0
                      and sharpness < best_sharpness * min_sharpness_ratio):
                    reason = "nitidez_inferior_al_umbral_relativo"
                else:
                    kept.append(sample)
                    continue
                rejected.append({
                    "camera": sample.camera,
                    "image": sample.image,
                    "quality": sample.quality,
                    "position": sample.position,
                    "score": sample.score,
                    "reason": reason,
                })
            kept_by_camera[camera] = kept

        max_kept = max((len(items) for items in kept_by_camera.values()), default=0)
        accepted_pairs = [
            {
                camera: kept_by_camera[camera][index].image
                for camera in self.cameras
                if index < len(kept_by_camera[camera])
            }
            for index in range(max_kept)
        ]
        return accepted_pairs, rejected


class AutoBurst:
    """Keep one fruit active until timeout or the capture zone is empty for a short gap."""

    def __init__(self, cameras: tuple[str, ...], gap_frames: int, max_pairs: int,
                 interval_seconds: float, min_change: float, require_all: bool = True,
                 max_duration_seconds: float | None = None):
        if gap_frames < 1:
            raise ValueError("gap_frames debe ser al menos 1")
        if max_duration_seconds is not None and max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds debe ser positivo")
        self.cameras = cameras
        self.gap_frames = gap_frames
        self.max_pairs = max_pairs
        self.interval_seconds = interval_seconds
        self.min_change = min_change
        self.require_all = require_all
        self.max_duration_seconds = max_duration_seconds
        self.active = False
        self.awaiting_exit = False
        self.started_at: float | None = None
        self.absent = 0
        self.collector = self._new_collector()
        self.last_collector: BurstCollector | None = None

    def _new_collector(self) -> BurstCollector:
        return BurstCollector(self.cameras, self.max_pairs,
                              self.interval_seconds, self.min_change, self.require_all)

    def _finish_burst(self, await_exit: bool) -> list[dict[str, Image.Image]]:
        self.last_collector = self.collector
        pairs = self.collector.pairs
        self.active = False
        self.started_at = None
        self.absent = 0
        self.awaiting_exit = await_exit
        self.collector = self._new_collector()
        return pairs

    def observe(self, images: dict[str, Image.Image],
                results: dict[str, tuple[QualityResult, PositionResult]],
                now: float) -> list[dict[str, Image.Image]] | None:
        present = any(results[camera][1].subject_bounds is not None for camera in self.cameras)
        if self.awaiting_exit:
            if present:
                self.absent = 0
            else:
                self.absent += 1
                if self.absent >= self.gap_frames:
                    self.awaiting_exit = False
                    self.absent = 0
            return None

        if present:
            if not self.active:
                self.active = True
                self.started_at = now
            self.absent = 0
            self.collector.offer(images, results, now)
            if self.max_duration_seconds is not None:
                timed_out = self.started_at is not None and (now - self.started_at >= self.max_duration_seconds)
                if timed_out or self.collector.full:
                    return self._finish_burst(await_exit=True)
            return None

        if self.active:
            self.absent += 1
        if not self.active or self.absent < self.gap_frames:
            return None
        return self._finish_burst(await_exit=False)
