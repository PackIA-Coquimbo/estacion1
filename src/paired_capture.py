"""PackIA estación 1: una fruta, una o dos vistas, un manifiesto de entrega."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from uuid import uuid4

from PIL import Image, ImageOps

from .camera import frame_to_image, open_camera
from .client_e2 import publish, safe_id
from .config import CaptureConfig
from .detector import evaluate_position
from .image_quality import evaluate_quality, roi_bounds
from .output_image import prepare_output
from .passage import PassageSelector


def process_capture(images: dict[str, Image.Image], lot_id: str, fruit_id: str,
                    configs: dict[str, CaptureConfig], output_dir: Path, evidence_dir: Path,
                    references: dict[str, Image.Image] | None = None,
                    manual_confirmed: bool = False,
                    output_framing: str = "crop") -> tuple[dict, dict[str, Path], Path]:
    """Valida cada vista. Si alguna falla, ninguna se ofrece a estación 2."""
    safe_id(lot_id)
    safe_id(fruit_id)
    if not 1 <= len(images) <= 2 or images.keys() != configs.keys():
        raise ValueError("Se necesitan una o dos imágenes con configuración correspondiente")
    references = references or {}
    normalized = {camera: ImageOps.exif_transpose(image).convert("RGB")
                  for camera, image in images.items()}
    views = []
    all_reasons = []
    accepted = True
    needs_review = False
    subject_bounds = {}
    for camera, image in normalized.items():
        safe_id(camera)
        config = configs[camera]
        position = evaluate_position(image, references.get(camera), config, manual_confirmed)
        subject_bounds[camera] = position.subject_bounds
        quality = evaluate_quality(image, config, position.subject_bounds)
        reasons = list(quality.reasons)
        if position.reason:
            reasons.append(position.reason)
        if position.reason in {"confirmar_posicion_o_calibrar_fondo", "referencia_resolucion_distinta"}:
            needs_review = True
        accepted &= quality.accepted and position.correct
        all_reasons.extend(f"{camera}:{reason}" for reason in reasons)
        views.append({
            "camara": camera,
            "imagen_valida": quality.accepted,
            "posicion_correcta": position.correct,
            "metodo_posicion": position.method,
            "metricas_calidad": quality.metrics,
            "metricas_posicion": position.metrics,
            "motivos": reasons,
        })

    now = datetime.now(timezone.utc)
    metadata = {
        "version_interfaz": 2,
        "estacion_origen": 1,
        "estacion_destino": 2 if accepted else None,
        "id_lote": lot_id,
        "id_fruta": fruit_id,
        "id_captura": f"captura_{now.strftime('%Y%m%dT%H%M%S%fZ')}_{uuid4().hex[:8]}",
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "estado_captura": "aceptada" if accepted else ("revision_manual" if needs_review else "repetir_captura"),
        "vistas": views,
        "motivos": all_reasons,
    }
    saved_images = {}
    for view in views:
        camera = view["camara"]
        source = normalized[camera]
        if accepted:
            saved, framing, box = prepare_output(
                source, subject_bounds[camera], configs[camera].roi, output_framing
            )
        else:
            saved, framing, box = source, "original_evidencia", None
        saved_images[camera] = saved
        view["resolucion_origen_px"] = list(source.size)
        view["resolucion_guardada_px"] = list(saved.size)
        view["encuadre_salida"] = framing
        view["recorte_origen_xyxy"] = list(box) if box else None
    target = output_dir if accepted else evidence_dir / "rechazadas"
    photos, manifest = publish(saved_images, metadata, target)
    return metadata, photos, manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PackIA estación 1: captura por fruta en cinta")
    parser.add_argument("--lot", required=True, help="Identificador de lote")
    parser.add_argument("--fruit", default="fruta_001", help="ID inicial de fruta")
    parser.add_argument("--camera", type=int, default=0, help="Índice de la primera cámara")
    parser.add_argument("--camera-2", type=int, help="Índice de la segunda cámara, opcional")
    parser.add_argument("--capture-width", type=int, default=1280,
                        help="Ancho solicitado a cada cámara (por defecto 1280)")
    parser.add_argument("--capture-height", type=int, default=720,
                        help="Alto solicitado a cada cámara (por defecto 720)")
    parser.add_argument("--image", type=Path, help="Probar con una foto, sin cámara")
    parser.add_argument("--image-2", type=Path, help="Segunda foto de la misma fruta")
    parser.add_argument("--reference", type=Path, help="Cinta vacía de cámara 1")
    parser.add_argument("--reference-2", type=Path, help="Cinta vacía de cámara 2")
    parser.add_argument("--roi", default="0.25,0.20,0.75,0.80", help="Guía cámara 1: x1,y1,x2,y2")
    parser.add_argument("--roi-2", default="0.25,0.20,0.75,0.80", help="Guía cámara 2")
    parser.add_argument("--confirm-position", action="store_true", help="Confirmación visual del operador")
    parser.add_argument("--auto", action="store_true", help="Una captura por paso; requiere fondo de cada cámara")
    parser.add_argument("--gap-frames", type=int, default=3, help="Fotogramas sin fruta para cerrar un paso")
    parser.add_argument("--output", type=Path, default=Path("salidas_estacion2"))
    parser.add_argument("--output-framing", choices=("crop", "pad"), default="crop",
                        help="Recortar alrededor de la fruta o conservar todo con bordes")
    parser.add_argument("--evidence", type=Path, default=Path("evidencia_estacion1"))
    return parser.parse_args()


def next_fruit_id(fruit_id: str) -> str:
    match = re.fullmatch(r"(.*?)(\d+)", fruit_id)
    if match:
        return f"{match.group(1)}{int(match.group(2)) + 1:0{len(match.group(2))}d}"
    return f"{fruit_id}_002"


def _report(metadata: dict, photos: dict[str, Path], manifest: Path) -> None:
    print(json.dumps({
        "id_fruta": metadata["id_fruta"],
        "estado": metadata["estado_captura"],
        "motivos": metadata["motivos"],
        "imagenes": {camera: str(path) for camera, path in photos.items()},
        "manifiesto": str(manifest),
    }, ensure_ascii=False))


def camera_loop(args: argparse.Namespace, configs: dict[str, CaptureConfig],
                references: dict[str, Image.Image]) -> int:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Falta opencv-python: instala requirements.txt") from exc
    indices = {"camara_0": args.camera}
    if args.camera_2 is not None:
        if args.camera_2 == args.camera:
            raise ValueError("Las dos cámaras deben tener índices distintos")
        indices["camara_1"] = args.camera_2
    captures = {}
    try:
        for camera, index in indices.items():
            captures[camera] = open_camera("opencv", index, args.capture_width, args.capture_height)
            actual_width = round(captures[camera].get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = round(captures[camera].get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"{camera} (índice {index}): captura {actual_width}×{actual_height} px; "
                  "JPG aceptado 480×640 px")
        selector = PassageSelector(tuple(indices), args.gap_frames)
        successful = 0
        read_failures = 0
        print("B: calibrar cinta vacía | C: capturar fruta | Q/Esc: salir")
        if args.auto:
            print("Automático: una fruta a la vez; espera su salida y escoge la mejor vista de cada cámara")
        while True:
            frames = {}
            for camera, cap in captures.items():
                ok, frame = cap.read()
                if not ok:
                    frames.clear()
                    break
                frames[camera] = frame
            if not frames:
                read_failures += 1
                if read_failures >= 20:
                    raise RuntimeError("Una cámara dejó de entregar fotogramas")
                time.sleep(0.05)
                continue
            read_failures = 0
            images = {camera: frame_to_image(frame) for camera, frame in frames.items()}
            results = {}
            for camera, image in images.items():
                position = evaluate_position(image, references.get(camera), configs[camera])
                quality = evaluate_quality(image, configs[camera], position.subject_bounds)
                results[camera] = quality, position

            if args.auto and all(camera in references for camera in indices):
                selected = selector.observe(images, results)
                if selected is not None:
                    metadata, photos, manifest = process_capture(
                        selected, args.lot, args.fruit, configs, args.output, args.evidence,
                        references, output_framing=args.output_framing
                    )
                    _report(metadata, photos, manifest)
                    successful += metadata["estado_captura"] == "aceptada"
                    args.fruit = next_fruit_id(args.fruit)

            previews = []
            for camera, frame in frames.items():
                preview = cv2.resize(frame, (640, 360))
                config = configs[camera]
                x1, y1, x2, y2 = roi_bounds((640, 360), config.roi)
                quality, position = results[camera]
                ready = quality.accepted and position.correct
                color = (40, 220, 40) if ready else (0, 180, 255)
                cv2.rectangle(preview, (x1, y1), (x2, y2), color, 2)
                status = "LISTA" if ready else ("CALIBRAR/CONFIRMAR" if camera not in references else "AJUSTAR")
                cv2.putText(preview, f"{camera}: {status}", (10, 27),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
                reasons = list(quality.reasons)
                if position.reason:
                    reasons.append(position.reason)
                cv2.putText(preview, ",".join(reasons)[:55], (10, 52),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.43, color, 1)
                previews.append(preview)
            display = cv2.hconcat(previews) if len(previews) == 2 else previews[0]
            cv2.putText(display, "B: fondo vacio  C: capturar  Q: salir", (10, 345),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.imshow("PackIA - Estacion 1 - frutas en cinta", display)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("b"):
                args.evidence.mkdir(parents=True, exist_ok=True)
                for camera, image in images.items():
                    references[camera] = image.copy()
                    image.save(args.evidence / f"fondo_vacio_{camera}.jpg", quality=95)
                selector = PassageSelector(tuple(indices), args.gap_frames)
                print("Fondos de cinta vacía calibrados; retirar frutas antes de pulsar B")
            if key == ord("c") and not args.auto:
                metadata, photos, manifest = process_capture(
                    images, args.lot, args.fruit, configs, args.output, args.evidence, references,
                    manual_confirmed=not all(camera in references for camera in indices),
                    output_framing=args.output_framing
                )
                _report(metadata, photos, manifest)
                successful += metadata["estado_captura"] == "aceptada"
                if metadata["estado_captura"] == "aceptada":
                    args.fruit = next_fruit_id(args.fruit)
        return 0 if successful else 1
    finally:
        for cap in captures.values():
            cap.release()
        cv2.destroyAllWindows()


def main() -> int:
    args = parse_args()
    try:
        if args.capture_width < 640 or args.capture_height < 480:
            raise ValueError("La captura solicitada debe ser al menos 640×480")
        if args.image_2 and not args.image:
            raise ValueError("--image-2 requiere --image")
        if args.reference_2 and not (args.camera_2 is not None or args.image_2):
            raise ValueError("--reference-2 requiere segunda cámara o imagen")
        dual = bool(args.image_2) if args.image else args.camera_2 is not None
        names = ("camara_0", "camara_1") if dual else ("camara_0",)
        configs = {}
        references = {}
        for camera, roi_text, path in zip(names, (args.roi, args.roi_2), (args.reference, args.reference_2)):
            roi = tuple(float(value) for value in roi_text.split(","))
            if len(roi) != 4:
                raise ValueError("ROI requiere cuatro valores")
            configs[camera] = CaptureConfig(roi=roi)
            if path:
                with Image.open(path) as opened:
                    references[camera] = opened.copy()
        if args.image:
            images = {}
            for camera, path in zip(names, (args.image, args.image_2)):
                with Image.open(path) as opened:
                    images[camera] = opened.copy()
            metadata, photos, manifest = process_capture(
                images, args.lot, args.fruit, configs, args.output, args.evidence,
                references, args.confirm_position, args.output_framing
            )
            _report(metadata, photos, manifest)
            return 0 if metadata["estado_captura"] == "aceptada" else 2
        return camera_loop(args, configs, references)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
