"""PackIA estación 1: una fruta, una o dos vistas, un manifiesto de entrega."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from uuid import uuid4

from PIL import Image, ImageOps

from .burst import AutoBurst, BurstCollector
from .camera import frame_to_image, open_camera
from .client_e2 import publish, safe_id
from .config import CaptureConfig
from .detector import evaluate_position
from .image_quality import quality_for_position, roi_bounds
from .output_image import prepare_output
from .training_samples import save_samples


def process_capture(images: dict[str, Image.Image], lot_id: str, fruit_id: str,
                    configs: dict[str, CaptureConfig], output_dir: Path, evidence_dir: Path,
                    references: dict[str, Image.Image] | None = None,
                    manual_confirmed: bool = False,
                    output_framing: str = "crop",
                    burst_id: str | None = None, burst_index: int | None = None,
                    burst_total: int | None = None,
                    position_detector=None, expected_cameras=None) -> tuple[dict, dict[str, Path], Path]:
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
        position = (position_detector or evaluate_position)(image, references.get(camera), config, manual_confirmed)
        subject_bounds[camera] = position.subject_bounds
        quality = quality_for_position(image, config, position)
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
        "camaras_esperadas": list(expected_cameras or images.keys()),
        "vistas_incompletas": bool(expected_cameras and set(images)!=set(expected_cameras)),
        "motivos": all_reasons,
    }
    if burst_id is not None:
        metadata.update(id_rafaga=safe_id(burst_id), indice_rafaga=burst_index,
                        total_rafaga=burst_total)
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


def process_burst(pairs: list[dict[str, Image.Image]], lot_id: str, fruit_id: str,
                  configs: dict[str, CaptureConfig], output_dir: Path, evidence_dir: Path,
                  references: dict[str, Image.Image], output_framing: str = "crop", position_detector=None) -> int:
    """Publish every synchronized pair under one fruit and one burst ID."""
    if not pairs:
        print("Ráfaga sin vistas válidas; gira la fruta dentro de ambas guías")
        return 0
    if position_detector and len(pairs) < 2:
        print("Ráfaga insuficiente: se requieren al menos dos pares válidos; repetir fruta")
        return 0
    burst_id = f"rafaga_{uuid4().hex[:12]}"
    accepted = 0
    for index, images in enumerate(pairs, 1):
        metadata, photos, manifest = process_capture(
            images, lot_id, fruit_id, {camera:configs[camera] for camera in images}, output_dir, evidence_dir,
            references, output_framing=output_framing,
            burst_id=burst_id, burst_index=index, burst_total=len(pairs),
            position_detector=position_detector, expected_cameras=tuple(configs)
        )
        _report(metadata, photos, manifest)
        accepted += metadata["estado_captura"] == "aceptada"
    print(f"Ráfaga {burst_id}: {accepted}/{len(pairs)} pares aceptados para {fruit_id}")
    return accepted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PackIA estación 1: captura por fruta en cinta")
    parser.add_argument("--detector", choices=("yolo", "background"), default="yolo")
    parser.add_argument("--yolo-model", type=Path, default=Path(__file__).resolve().parents[1] / "models" / "yolov8n.pt")
    parser.add_argument("--yolo-confidence", type=float, default=0.55)
    parser.add_argument("--yolo-confidence-2", type=float, default=None,
                        help="Umbral independiente de cámara 1; no bajarlo sin validar")
    parser.add_argument("--min-sharpness-2", type=float, default=None)
    parser.add_argument("--min-contrast-2", type=float, default=None)
    parser.add_argument("--training-dir", type=Path, default=Path('dataset_naranjas/raw'))
    parser.add_argument("--collect-training", action='store_true',
                        help='Solo ejemplos: T guarda y N cambia el ID de fruta, sin capturas automáticas')
    parser.add_argument("--min-sharpness", type=float, default=65.0)
    parser.add_argument("--min-contrast", type=float, default=10.0,
                        help="Contraste mínimo dentro de la fruta (YOLO)")
    parser.add_argument("--lot", required=True, help="Identificador de lote")
    parser.add_argument("--fruit", default=f"fruta_{uuid4().hex[:8]}_001", help="ID inicial de fruta")
    parser.add_argument("--camera", type=camera_source, default=0,
                        help="Índice o dispositivo de la primera cámara")
    parser.add_argument("--camera-2", type=camera_source,
                        help="Índice o dispositivo de la segunda cámara, opcional")
    parser.add_argument("--capture-width", type=int, default=1280,
                        help="Ancho solicitado a cada cámara (por defecto 1280)")
    parser.add_argument("--capture-height", type=int, default=720,
                        help="Alto solicitado a cada cámara (por defecto 720)")
    parser.add_argument("--image", type=Path, help="Probar con una foto, sin cámara")
    parser.add_argument("--image-2", type=Path, help="Segunda foto de la misma fruta")
    parser.add_argument("--reference", type=Path, help="Cinta vacía de cámara 1")
    parser.add_argument("--reference-2", type=Path, help="Cinta vacía de cámara 2")
    parser.add_argument("--roi", default="0.25,0.20,0.75,0.80", help="Zona de detección cámara 1: x1,y1,x2,y2")
    parser.add_argument("--roi-2", default="0.25,0.20,0.75,0.80", help="Zona de detección cámara 2")
    parser.add_argument("--guide-roi", default="0.36,0.25,0.64,0.75",
                        help="Cuadro visible cámara 1: x1,y1,x2,y2")
    parser.add_argument("--guide-roi-2", default="0.36,0.25,0.64,0.75",
                        help="Cuadro visible cámara 2")
    parser.add_argument("--confirm-position", action="store_true", help="Confirmación visual del operador")
    parser.add_argument("--auto", action="store_true", help="Ráfaga por fruta al pasar; calibración B solo con detector background")
    parser.add_argument("--gap-frames", type=int, default=3, help="Fotogramas sin fruta para cerrar un paso")
    parser.add_argument("--burst-count", type=int, default=12,
                        help="Máximo de pares por fruta en ráfaga (1 a 32; por defecto 12)")
    parser.add_argument("--burst-interval-ms", type=int, default=350,
                        help="Intervalo mínimo entre pares (por defecto 350 ms)")
    parser.add_argument("--burst-min-change", type=float, default=1.5,
                        help="Cambio visual mínimo entre vistas (1.5); 0 conserva todas")
    parser.add_argument("--output", type=Path, default=Path("salidas_estacion2"))
    parser.add_argument("--output-framing", choices=("crop", "pad", "fruit"), default="fruit",
                        help="Recortar alrededor de la fruta o conservar todo con bordes")
    parser.add_argument("--evidence", type=Path, default=Path("evidencia_estacion1"))
    return parser.parse_args()


def camera_source(value: str) -> int | str:
    return int(value) if value.isdecimal() else value


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
    position_detector = getattr(args, "position_detector", None)
    captures = {}
    try:
        for camera, index in indices.items():
            captures[camera] = open_camera("opencv", index, args.capture_width, args.capture_height)
            actual_width = round(captures[camera].get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = round(captures[camera].get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"{camera} (dispositivo {index}): captura {actual_width}×{actual_height} px; "
                  "JPG aceptado 480×640 px")
        cameras = tuple(indices)
        interval = args.burst_interval_ms / 1000
        auto_burst = AutoBurst(cameras, args.gap_frames, args.burst_count,
                               interval, args.burst_min_change,require_all=not bool(position_detector))
        manual_burst = None
        collection_mode=getattr(args,'collect_training',False)
        successful = 0
        read_failures = 0
        print("C: foto | R: ráfaga | T: ejemplo para entrenar | N: siguiente fruta | Q: salir")
        if args.auto:
            print("Automático: una fruta a la vez; guarda varios pares mientras cruza la zona")

        def save_burst(pairs: list[dict[str, Image.Image]]) -> None:
            nonlocal successful
            accepted = process_burst(pairs, args.lot, args.fruit, configs,
                                     args.output, args.evidence, references,
                                     args.output_framing, position_detector=position_detector)
            successful += accepted
            if accepted:
                args.fruit = next_fruit_id(args.fruit)
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
                position = (position_detector or evaluate_position)(image, references.get(camera), configs[camera])
                quality = quality_for_position(image, configs[camera], position)
                results[camera] = quality, position

            if args.auto and not collection_mode and (position_detector or all(camera in references for camera in indices)):
                selected = auto_burst.observe(images, results, time.monotonic())
                if selected is not None:
                    save_burst(selected)

            previews = []
            for camera, frame in frames.items():
                preview = cv2.resize(frame, (640, 360))
                config = configs[camera]
                x1, y1, x2, y2 = roi_bounds((640, 360), config.guide_roi)
                quality, position = results[camera]
                ready = quality.accepted and position.correct
                color = (40, 220, 40) if ready else (0, 180, 255)
                cv2.rectangle(preview, (x1, y1), (x2, y2), color, 2)
                if position.subject_bounds and position.method == 'yolo':
                    bx1,by1,bx2,by2 = position.subject_bounds
                    cv2.rectangle(preview, (round(bx1*640/frame.shape[1]),round(by1*360/frame.shape[0])),
                                  (round(bx2*640/frame.shape[1]),round(by2*360/frame.shape[0])), color, 2)
                status = "LISTA" if ready else ("CALIBRAR/CONFIRMAR" if not position_detector and camera not in references else "AJUSTAR")
                cv2.putText(preview, f"{camera}: {status}", (10, 27),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
                reasons = list(quality.reasons)
                if position.reason:
                    reasons.append(position.reason)
                cv2.putText(preview, ",".join(reasons)[:55], (10, 52),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.43, color, 1)
                confidence = position.metrics.get('confianza_yolo',position.metrics.get('mejor_confianza_yolo',0))
                cv2.putText(preview, f"YOLO {confidence:.2f}  foco {quality.metrics['nitidez_laplaciano']:.0f}  luz {quality.metrics['brillo']:.0f}",
                            (10,75),cv2.FONT_HERSHEY_SIMPLEX,0.45,color,1)
                previews.append(preview)
            display = cv2.hconcat(previews) if len(previews) == 2 else previews[0]
            count = (len(auto_burst.collector.pairs) if args.auto else
                     len(manual_burst.pairs) if manual_burst else 0)
            collector=auto_burst.collector if args.auto else manual_burst
            if collector and not collector.require_all:
                for index,camera in enumerate(cameras):
                    cv2.putText(display,f"{camera}: {collector.camera_counts[camera]}/{args.burst_count}",
                                (10+index*640,320),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
            mode = "DATOS" if collection_mode else "AUTO" if args.auto else "RAFAGA" if manual_burst else "LISTO"
            cv2.putText(display,args.fruit,(10,296),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
            controls='DATOS T:guardar ejemplo N:nueva fruta Q:salir' if collection_mode else f"{mode} C:foto R:rafaga T:ejemplo N:fruta Q:salir"
            cv2.putText(display, controls,
                        (10, 345),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.imshow("PackIA - Estacion 1 - frutas en cinta", display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('t'):
                paths=save_samples(images,args.fruit,args.lot,results,
                                   getattr(args,'training_dir',Path('dataset_naranjas/raw')))
                print(f'Ejemplos guardados para revisión ({args.fruit}): {paths}')
            if key == ord('n'):
                if manual_burst is None and (collection_mode or not auto_burst.active):
                    args.fruit=next_fruit_id(args.fruit)
                    print(f'Siguiente fruta física: {args.fruit}')
                else:
                    print('Termina la ráfaga o retira la fruta antes de cambiar ID; usa recolectar_ejemplos.bat para datos')
            if key in (ord("q"), 27):
                if manual_burst is not None:
                    save_burst(manual_burst.pairs)
                elif args.auto and auto_burst.collector.pairs:
                    save_burst(auto_burst.collector.pairs)
                break
            if key == ord("b") and manual_burst is not None:
                print("Termina la ráfaga con R antes de calibrar el fondo vacío")
            elif key == ord("b"):
                if args.auto and auto_burst.collector.pairs:
                    save_burst(auto_burst.collector.pairs)
                args.evidence.mkdir(parents=True, exist_ok=True)
                for camera, image in images.items():
                    references[camera] = image.copy()
                    image.save(args.evidence / f"fondo_vacio_{camera}.jpg", quality=95)
                auto_burst = AutoBurst(cameras, args.gap_frames, args.burst_count,
                                       interval, args.burst_min_change,require_all=not bool(position_detector))
                print("Fondos de cinta vacía calibrados; retirar frutas antes de pulsar B")
            if key == ord("r") and not args.auto and not collection_mode:
                if manual_burst is not None:
                    save_burst(manual_burst.pairs)
                    manual_burst = None
                elif position_detector or all(camera in references for camera in cameras):
                    manual_burst = BurstCollector(cameras, args.burst_count,
                                                  interval, args.burst_min_change,require_all=not bool(position_detector))
                    print(f"Ráfaga iniciada para {args.fruit}; gira la naranja y pulsa R para terminar")
                else:
                    print("Calibra primero el fondo vacío con B para usar ráfaga")
            capture_single = key == ord("c") and not args.auto and not collection_mode and manual_burst is None
            if manual_burst is not None:
                manual_burst.offer(images, results, time.monotonic())
                if manual_burst.full:
                    save_burst(manual_burst.pairs)
                    manual_burst = None
            if capture_single:
                metadata, photos, manifest = process_capture(
                    images, args.lot, args.fruit, configs, args.output, args.evidence, references,
                    manual_confirmed=not all(camera in references for camera in indices),
                    output_framing=args.output_framing, position_detector=position_detector
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
        if not 0 < args.yolo_confidence <= 1:
            raise ValueError("Confianza YOLO debe estar entre 0 y 1")
        if args.capture_width < 640 or args.capture_height < 480:
            raise ValueError("La captura solicitada debe ser al menos 640×480")
        if not 1 <= args.burst_count <= 32 or args.burst_interval_ms < 1 or args.burst_min_change < 0:
            raise ValueError("Ráfaga: pares 1 a 32, intervalo positivo y cambio mínimo no negativo")
        if args.image_2 and not args.image:
            raise ValueError("--image-2 requiere --image")
        if args.reference_2 and not (args.camera_2 is not None or args.image_2):
            raise ValueError("--reference-2 requiere segunda cámara o imagen")
        args.position_detector = None
        if args.detector == "yolo":
            from .yolo_detector import YoloOrangeDetector
            args.position_detector = YoloOrangeDetector(args.yolo_model, args.yolo_confidence)
        dual = bool(args.image_2) if args.image else args.camera_2 is not None
        names = ("camara_0", "camara_1") if dual else ("camara_0",)
        configs = {}
        references = {}
        for camera, roi_text, guide_text, path in zip(
                names, (args.roi, args.roi_2), (args.guide_roi, args.guide_roi_2),
                (args.reference, args.reference_2)):
            roi = tuple(float(value) for value in roi_text.split(","))
            guide_roi = tuple(float(value) for value in guide_text.split(","))
            if len(roi) != 4 or len(guide_roi) != 4:
                raise ValueError("ROI y guía requieren cuatro valores")
            configs[camera] = CaptureConfig(roi=roi, guide_roi=guide_roi,
                min_sharpness=(args.min_sharpness_2 if camera=='camara_1' and args.min_sharpness_2 is not None else args.min_sharpness),
                min_contrast=(args.min_contrast_2 if camera=='camara_1' and args.min_contrast_2 is not None else args.min_contrast) if args.detector=='yolo' else 28.0,
                yolo_confidence=args.yolo_confidence_2 if camera=='camara_1' else None)
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
                references, args.confirm_position, args.output_framing,
                position_detector=args.position_detector
            )
            _report(metadata, photos, manifest)
            return 0 if metadata["estado_captura"] == "aceptada" else 2
        return camera_loop(args, configs, references)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
