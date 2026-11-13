"""Control de calidad de captura. No infiere madurez ni defectos de la fruta."""

from dataclasses import asdict, dataclass

import numpy as np
from PIL import Image

from .config import CaptureConfig


@dataclass(frozen=True)
class QualityResult:
    accepted: bool
    reasons: tuple[str, ...]
    metrics: dict[str, float | int]

    def as_dict(self) -> dict:
        return asdict(self)


def roi_bounds(size: tuple[int, int], roi: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    width, height = size
    x1, y1, x2, y2 = roi
    return (int(x1 * width), int(y1 * height), int(x2 * width), int(y2 * height))


def evaluate_quality(image: Image.Image, config: CaptureConfig,
                     subject_bounds: tuple[int, int, int, int] | None = None) -> QualityResult:
    """Mide la fruta detectada; si no hay detección usa la zona de inspección."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    region = rgb.crop(subject_bounds or roi_bounds(rgb.size, config.roi))
    if region.width < 3 or region.height < 3:
        raise ValueError("ROI demasiado pequeña para evaluar nitidez")
    gray = np.asarray(region.convert("L"), dtype=np.float32)
    # Reducir el costo conservando la proporción y la resolución entregada.
    scale = min(1.0, 640 / region.width, 480 / region.height)
    sample_size = (max(3, round(region.width * scale)), max(3, round(region.height * scale)))
    sample = np.asarray(region.convert("L").resize(sample_size), dtype=np.float32)
    laplacian = (-4 * sample[1:-1, 1:-1] + sample[:-2, 1:-1] + sample[2:, 1:-1]
                 + sample[1:-1, :-2] + sample[1:-1, 2:])
    brightness = float(gray.mean())
    contrast = float(gray.std())
    sharpness = float(laplacian.var())
    clipped = float(np.mean((gray <= 8) | (gray >= 247)))
    metrics = {
        "ancho": width, "alto": height,
        "brillo": round(brightness, 2), "contraste": round(contrast, 2),
        "nitidez_laplaciano": round(sharpness, 2),
        "fraccion_saturada": round(clipped, 4),
    }
    reasons = []
    if width < config.min_width or height < config.min_height:
        reasons.append("resolucion_insuficiente")
    if brightness < config.min_brightness:
        reasons.append("imagen_oscura")
    if brightness > config.max_brightness:
        reasons.append("imagen_sobreexpuesta")
    if contrast < config.min_contrast:
        reasons.append("contraste_insuficiente")
    if sharpness < config.min_sharpness:
        reasons.append("imagen_borrosa")
    if clipped > config.max_clipped_fraction:
        reasons.append("sombras_o_luces_recortadas")
    return QualityResult(not reasons, tuple(reasons), metrics)
