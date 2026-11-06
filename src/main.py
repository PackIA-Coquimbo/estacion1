"""Station 1: photograph passing oranges and queue photos for station 2."""

import argparse
import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from .camera import open_camera
from .tracker import FruitTracker


ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "LogicaPackIA" / "captures" / "estacion1"
OUTBOX = ROOT / "LogicaPackIA" / "outbox_e2"
ZONE_X = (0.25, 0.75)
ZONE_Y = (0.35, 0.98)


def capture_zone(frame):
    height, width = frame.shape[:2]
    return (int(width * ZONE_X[0]), int(height * ZONE_Y[0]),
            int(width * ZONE_X[1]), int(height * ZONE_Y[1]))


def detect_oranges(frame):
    """Find fruit whose centre is in the conveyor capture zone."""
    height, width = frame.shape[:2]
    zone_x1, zone_y1, zone_x2, zone_y2 = capture_zone(frame)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    orange = cv2.inRange(hsv, (3, 40, 25), (35, 255, 255))
    green = cv2.inRange(hsv, (35, 20, 25), (88, 255, 220))
    red = cv2.bitwise_or(cv2.inRange(hsv, (0, 50, 25), (15, 255, 255)),
                         cv2.inRange(hsv, (170, 50, 25), (179, 255, 255)))
    mask = cv2.bitwise_or(cv2.bitwise_or(orange, green), red)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < width * height * 0.018:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        center_x, center_y = x + w / 2, y + h / 2
        if not (zone_x1 <= center_x <= zone_x2 and zone_y1 <= center_y <= zone_y2):
            continue
        margin = min(width, height) * 0.02
        if min(x, y, width - x - w, height - y - h) < margin:
            continue
        ratio = w / max(h, 1)
        perimeter = cv2.arcLength(contour, True)
        circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter else 0
        if 0.65 <= ratio <= 1.5 and circularity >= 0.32:
            candidates.append((area, (x, y, x + w, y + h)))
    return [box for _, box in sorted(candidates, reverse=True)]


def assess(frame, box):
    """Check framing, brightness, contrast and focus only."""
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = box
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return False, 0.0, "sin imagen"
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())
    contrast = float(gray.std())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    margin = min(x1, y1, width - x2, height - y2)
    if margin < min(width, height) * 0.02:
        return False, sharpness, "fuera de cuadro"
    if brightness < 45 or brightness > 215:
        return False, sharpness, "ajustar luz"
    if contrast < 18:
        return False, sharpness, "bajo contraste"
    if sharpness < 75:
        return False, sharpness, "imagen borrosa"
    return True, sharpness, "imagen lista"


def save_capture(frame, box, score, captures_dir, outbox_dir, camera_id, track_id):
    captures_dir.mkdir(parents=True, exist_ok=True)
    outbox_dir.mkdir(parents=True, exist_ok=True)
    capture_id = f"{camera_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    path = captures_dir / f"naranja_{capture_id}.jpg"
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = box
    pad = int(max(x2 - x1, y2 - y1) * 0.08)
    crop_box = (max(0, x1 - pad), max(0, y1 - pad),
                min(width, x2 + pad), min(height, y2 + pad))
    cx1, cy1, cx2, cy2 = crop_box
    fruit_photo = frame[cy1:cy2, cx1:cx2]
    if fruit_photo.size == 0 or not cv2.imwrite(str(path), fruit_photo, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        raise OSError(f"No se pudo guardar {path}")
    outgoing_photo = outbox_dir / path.name
    shutil.copy2(path, outgoing_photo)
    metadata = {
        "capture_id": capture_id,
        "camera_id": camera_id,
        "camera_track_id": track_id,
        "captured_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "object_type": "naranja",
        "image_width": fruit_photo.shape[1],
        "image_height": fruit_photo.shape[0],
        "source_image_width": width,
        "source_image_height": height,
        "bbox_xyxy": list(box),
        "crop_xyxy": list(crop_box),
        "sharpness": round(score, 2),
        "photo": outgoing_photo.name,
        "delivery_status": "pending",
    }
    pending = outbox_dir / f"{capture_id}.json"
    temporary = pending.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, pending)
    print(f"Foto guardada: {path}\nPendiente para estacion 2: {pending}", flush=True)


def run(camera_index=0, backend="auto", headless=False, width=1280, height=720,
        data_dir=None, camera_id=None):
    if camera_id is None:
        camera_id = (f"cam{camera_index}" if isinstance(camera_index, int) else
                     "cam_" + re.sub(r"[^A-Za-z0-9_-]", "_", Path(camera_index).name))
    if not camera_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("camera_id solo admite letras, numeros, guion y guion bajo")
    captures_dir = Path(data_dir) / "captures" if data_dir else CAPTURES
    outbox_dir = Path(data_dir) / "outbox_e2" if data_dir else OUTBOX
    try:
        camera = open_camera(backend, camera_index, width, height)
    except (RuntimeError, OSError) as exc:
        print(f"Error de camara: {exc}", flush=True)
        return 1
    window = "Estacion 1 - Captura para estacion 2"
    if not headless:
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window, 1440, 810)
        cv2.moveWindow(window, 40, 40)
    exit_hint = "Ctrl+C" if headless else "Q o Esc"
    print(f"Estacion 1 activa. Una foto nitida por naranja. Salir: {exit_hint}.", flush=True)
    print("Entrega a estacion 2 pendiente de definir receptor; fotos en outbox_e2.", flush=True)
    tracker = FruitTracker()
    exit_code = 0
    try:
        while True:
            ok, frame = camera.read()
            if not ok or frame is None:
                print("No se pudo leer la camara.", flush=True)
                exit_code = 1
                break
            now = time.monotonic()
            boxes = detect_oranges(frame)
            assignments = tracker.update(boxes, now)
            message = f"{len(boxes)} naranja(s) en zona de captura" if boxes else "Esperando naranja"
            color = (220, 220, 220)
            for track, box in assignments:
                good, score, reason = assess(frame, box)
                if not track.photographed:
                    color = (0, 200, 255)
                    if good and score > track.best_score:
                        track.best_frame = frame.copy()
                        track.best_box = box
                        track.best_score = score
                    if track.best_frame is not None and now - track.first_seen >= 0.45:
                        save_capture(track.best_frame, track.best_box, track.best_score,
                                     captures_dir, outbox_dir, camera_id, track.track_id)
                        track.photographed = True
                        message = f"Foto de naranja {track.track_id} lista para estacion 2"
                        color = (0, 220, 0)
            if not headless:
                display = frame.copy()
                zx1, zy1, zx2, zy2 = capture_zone(frame)
                cv2.rectangle(display, (zx1, zy1), (zx2, zy2), (255, 180, 0), 2)
                cv2.putText(display, "ZONA DE CAPTURA", (zx1 + 8, zy1 + 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 180, 0), 2)
                for track, detected_box in assignments:
                    box_color = (0, 220, 0) if track.photographed else (0, 200, 255)
                    cv2.rectangle(display, detected_box[:2], detected_box[2:], box_color, 3)
                    cv2.putText(display, f"{camera_id} #{track.track_id}",
                                (detected_box[0], max(90, detected_box[1] - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)
                cv2.rectangle(display, (0, 0), (display.shape[1], 80), (20, 20, 20), -1)
                cv2.putText(display, message, (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                cv2.putText(display, "Estacion 1: solo foto | Envio a E2: pendiente | Q: salir", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (230, 230, 230), 2)
                cv2.imshow(window, display)
                if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q"), 27):
                    break
    except KeyboardInterrupt:
        print("Captura detenida.", flush=True)
    finally:
        camera.release()
        if not headless:
            cv2.destroyAllWindows()
    return exit_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", default="0", help="Indice numerico o ruta V4L2 de camara USB")
    parser.add_argument("--camera-id", help="Identificador de esta camara, por ejemplo cam_izquierda")
    parser.add_argument("--backend", choices=("auto", "opencv", "picamera2"), default="auto")
    parser.add_argument("--headless", action="store_true", help="Ejecutar sin ventana grafica")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--data-dir", type=Path, help="Directorio persistente para fotos y bandeja E2")
    args = parser.parse_args()
    camera_source = int(args.camera) if args.camera.isdecimal() else args.camera
    raise SystemExit(run(camera_source, args.backend, args.headless,
                         args.width, args.height, args.data_dir, args.camera_id))
