"""Prepara las fotos aceptadas para la resolución acordada con estación 2."""

from PIL import Image, ImageOps


OUTPUT_SIZE = (480, 640)  # ancho, alto en píxeles


def prepare_output(image: Image.Image,
                   subject_bounds: tuple[int, int, int, int] | None,
                   roi: tuple[float, float, float, float],
                   framing: str = "crop") -> tuple[Image.Image, str, tuple[int, int, int, int] | None]:
    """Crea una imagen 480x640 sin deformar la fruta.

    El recorte se centra en la fruta detectada; sin detección usa el centro de
    la guía. Si la fruta no cabe completa, conserva el fotograma con bordes.
    """
    if framing not in {"crop", "pad"}:
        raise ValueError("El encuadre de salida debe ser crop o pad")
    source = ImageOps.exif_transpose(image).convert("RGB")
    width, height = source.size
    target_width, target_height = OUTPUT_SIZE

    def padded():
        result = ImageOps.pad(source, OUTPUT_SIZE, method=Image.Resampling.LANCZOS,
                              color=(32, 32, 32))
        return result, "pad", None

    if framing == "pad":
        return padded()

    ratio = target_width / target_height
    if width / height >= ratio:
        crop_width, crop_height = round(height * ratio), height
    else:
        crop_width, crop_height = width, round(width / ratio)
    crop_width = min(width, crop_width)
    crop_height = min(height, crop_height)

    if subject_bounds:
        sx1, sy1, sx2, sy2 = subject_bounds
        margin = round(0.10 * max(sx2 - sx1, sy2 - sy1))
        sx1, sy1 = max(0, sx1 - margin), max(0, sy1 - margin)
        sx2, sy2 = min(width, sx2 + margin), min(height, sy2 + margin)
        if sx2 - sx1 > crop_width or sy2 - sy1 > crop_height:
            return padded()
        center_x, center_y = (sx1 + sx2) / 2, (sy1 + sy2) / 2
    else:
        x1, y1, x2, y2 = roi
        center_x = (x1 + x2) * width / 2
        center_y = (y1 + y2) * height / 2

    left = max(0, min(width - crop_width, round(center_x - crop_width / 2)))
    top = max(0, min(height - crop_height, round(center_y - crop_height / 2)))
    if subject_bounds:
        left = max(max(0, sx2 - crop_width), min(left, min(width - crop_width, sx1)))
        top = max(max(0, sy2 - crop_height), min(top, min(height - crop_height, sy1)))
    box = (left, top, left + crop_width, top + crop_height)
    result = source.crop(box).resize(OUTPUT_SIZE, Image.Resampling.LANCZOS)
    return result, "crop", box
