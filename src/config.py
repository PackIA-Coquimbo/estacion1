"""Parámetros de captura de cada fruta; calibrar con la cinta y cámaras reales."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CaptureConfig:
    # Zona donde debe pasar una fruta individual, en fracciones del fotograma.
    roi: tuple[float, float, float, float] = (0.25, 0.20, 0.75, 0.80)
    min_width: int = 640
    min_height: int = 480
    min_brightness: float = 55.0
    max_brightness: float = 205.0
    min_contrast: float = 28.0
    min_sharpness: float = 65.0
    max_clipped_fraction: float = 0.12
    background_difference: int = 30
    min_occupancy: float = 0.035
    max_outside_occupancy: float = 0.08
    min_subject_width: int = 100
    min_subject_height: int = 100

    def __post_init__(self) -> None:
        x1, y1, x2, y2 = self.roi
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError("ROI debe ser x1,y1,x2,y2 entre 0 y 1")
