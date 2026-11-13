"""Comprobación de presencia y encuadre de una fruta sobre cinta homogénea."""

from dataclasses import asdict, dataclass

import numpy as np
from PIL import Image, ImageFilter

from .config import CaptureConfig
from .image_quality import roi_bounds


@dataclass(frozen=True)
class PositionResult:
    correct: bool
    method: str
    reason: str | None
    metrics: dict[str, float | int]
    subject_bounds: tuple[int, int, int, int] | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate_position(image: Image.Image, reference: Image.Image | None,
                      config: CaptureConfig, manual_confirmed: bool = False) -> PositionResult:
    if reference is None:
        if manual_confirmed:
            return PositionResult(True, "confirmacion_operador", None, {})
        return PositionResult(False, "sin_referencia", "confirmar_posicion_o_calibrar_fondo", {})
    if image.size != reference.size:
        return PositionResult(False, "fondo_calibrado", "referencia_resolucion_distinta", {})

    # Comparar fotos desenfocadas atenúa ruido de sensor y pequeños movimientos.
    def prepared(value: Image.Image) -> np.ndarray:
        return np.asarray(value.convert("L").filter(ImageFilter.GaussianBlur(3)).resize((320, 180)), dtype=np.int16)

    changed = np.abs(prepared(image) - prepared(reference)) >= config.background_difference
    x1, y1, x2, y2 = roi_bounds((320, 180), config.roi)
    inside = changed[y1:y2, x1:x2]
    outside = changed.copy()
    outside[y1:y2, x1:x2] = False
    outside_count = changed.size - inside.size
    occupied = float(inside.mean())
    spilled = float(outside.sum() / max(1, outside_count))
    metrics = {"ocupacion_roi": round(occupied, 4), "ocupacion_fuera_roi": round(spilled, 4)}
    points = np.argwhere(inside)
    bounds = None
    if len(points):
        top, left = points.min(axis=0)
        bottom, right = points.max(axis=0) + 1
        # La máscara 320x180 se convierte a coordenadas del fotograma original.
        bounds = (
            int((x1 + left) * image.width / 320),
            int((y1 + top) * image.height / 180),
            int((x1 + right) * image.width / 320),
            int((y1 + bottom) * image.height / 180),
        )
        metrics["ancho_fruta_px"] = bounds[2] - bounds[0]
        metrics["alto_fruta_px"] = bounds[3] - bounds[1]
    reason = None
    if occupied < config.min_occupancy:
        reason = "fruta_ausente_o_fuera_de_guia"
    elif spilled > config.max_outside_occupancy:
        reason = "fruta_fuera_de_guia"
    elif bounds and (metrics["ancho_fruta_px"] < config.min_subject_width
                     or metrics["alto_fruta_px"] < config.min_subject_height):
        reason = "fruta_demasiado_pequena"
    return PositionResult(reason is None, "fondo_calibrado", reason, metrics, bounds)
