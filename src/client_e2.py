"""Entrega por carpeta: todas las vistas JPEG antes del manifiesto JSON."""

import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import tempfile

from PIL import Image


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("ID: usar letras ASCII, números, _ o - (máximo 64)")
    return value


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".packia-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def encode_jpeg(image: Image.Image) -> bytes:
    stream = BytesIO()
    image.convert("RGB").save(stream, "JPEG", quality=95, subsampling=0)
    return stream.getvalue()


def publish(images: dict[str, Image.Image], metadata: dict,
            output_dir: Path) -> tuple[dict[str, Path], Path]:
    """Un JSON por fruta es la señal para E2; se escribe luego de ambas imágenes."""
    folder = output_dir / safe_id(metadata["id_lote"])
    capture_id = safe_id(metadata["id_captura"])
    manifest = folder / f"{capture_id}.json"
    if manifest.exists():
        raise FileExistsError(manifest)
    payload = dict(metadata)
    views = []
    photos = {}
    for view in metadata["vistas"]:
        camera = safe_id(view["camara"])
        if camera not in images:
            raise ValueError(f"Falta imagen de {camera}")
        path = folder / f"{capture_id}_{camera}.jpg"
        if path.exists():
            raise FileExistsError(path)
        data = encode_jpeg(images[camera])
        _atomic_bytes(path, data)
        photos[camera] = path
        views.append({**view, "imagen": path.name, "sha256": hashlib.sha256(data).hexdigest()})
    payload["vistas"] = views
    _atomic_bytes(manifest, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    return photos, manifest
