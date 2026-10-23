"""
PackIACamara - Sistema de Video e Inspección Inteligente de Naranjas
1. Detección continua en Video (25-30 FPS) con auto-ajuste de iluminación.
2. Memoria y Persistencia de Identidad: Reconoce si la naranja en pantalla sigue
   siendo la misma (evita ráfagas y fotos repetidas, incluso si se mueve o rota).
3. Detección de salida / entrada con tiempo de gracia (2 segundos de ausencia antes de rearmar).
4. Clasificación de Calidad en Tiempo Real:
   - BUEN ESTADO (ÓPTIMA)
   - DEFECTO LEVE (GOLPES / MANCHAS)
   - PODRIDA / EN MAL ESTADO (MOHO / NECROSIS)
5. Almacenamiento organizado por carpetas de calidad y registro en CSV.
"""

import os
import sys
import time
import csv
import threading
from datetime import datetime
import cv2
import numpy as np

# Soporte de sonido de obturador en Windows
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# Importar motor de iluminación adaptativa
try:
    from auto_camera import AutoLightingCamera
except ImportError:
    AutoLightingCamera = None

# Importar Ultralytics YOLOv8
try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False


class OrangeQualityClassifier:
    """
    Analizador de calidad superficial para cítricos:
    Detecta moho (Penicillium digitatum / italicum) y necrosis/podredumbre oscura.
    """
    @staticmethod
    def classify(crop_bgr):
        """
        Analiza el recorte de la fruta y retorna:
        (estado, pct_defectos, pct_moho, color_bgr)
        """
        if crop_bgr is None or crop_bgr.size == 0 or crop_bgr.shape[0] < 15 or crop_bgr.shape[1] < 15:
            return "BUEN ESTADO", 0.0, 0.0, (0, 255, 128)

        h, w = crop_bgr.shape[:2]
        
        # Máscara elíptica centrada para excluir fondo de la mesa/manos
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.ellipse(mask, (w // 2, h // 2), (int(w * 0.44), int(h * 0.44)), 0, 0, 360, 255, -1)
        total_pixels = cv2.countNonZero(mask)
        if total_pixels == 0:
            return "BUEN ESTADO", 0.0, 0.0, (0, 255, 128)

        # 1. Detección de Moho (Verdoso, cianáceo o blancuzco típico de hongos de cítricos)
        hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
        mold_lower = np.array([35, 25, 45], dtype=np.uint8)
        mold_upper = np.array([88, 255, 220], dtype=np.uint8)
        mold_mask = cv2.inRange(hsv, mold_lower, mold_upper) & mask
        mold_pixels = cv2.countNonZero(mold_mask)

        # 2. Detección de Necrosis / Manchas oscuras de podredumbre
        lab = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2LAB)
        l_channel, _, _ = cv2.split(lab)
        mean_l = float(np.mean(l_channel[mask > 0])) if total_pixels > 0 else 100.0
        
        # Manchas significativamente más oscuras que el promedio de la piel de la fruta
        dark_thresh = max(35, int(mean_l * 0.55))
        rot_mask = (l_channel < dark_thresh) & mask
        rot_pixels = cv2.countNonZero(rot_mask)

        # Defecto total combinado
        defect_mask = (mold_mask | rot_mask) & mask
        defect_pixels = cv2.countNonZero(defect_mask)

        mold_pct = (mold_pixels / float(total_pixels)) * 100.0
        defect_pct = (defect_pixels / float(total_pixels)) * 100.0

        # Reglas de decisión de calidad
        if mold_pct > 3.5 or defect_pct > 14.0:
            status = "PODRIDA / MAL ESTADO"
            color_bgr = (0, 0, 240)        # Rojo intenso
            folder = "podridas"
        elif defect_pct > 5.5 or mold_pct > 1.2:
            status = "DEFECTO LEVE"
            color_bgr = (0, 215, 255)      # Amarillo / Ámbar
            folder = "danadas"
        else:
            status = "BUEN ESTADO"
            color_bgr = (0, 255, 128)      # Verde esmeralda
            folder = "buen_estado"

        return status, defect_pct, mold_pct, color_bgr, folder


class OrangeDetectorAI:
    """
    Detector híbrido inteligente para naranjas (YOLOv8 + visión geométrica).
    """
    def __init__(self, confidence_threshold=0.28):
        self.conf_threshold = confidence_threshold
        self.yolo_model = None
        self.using_yolo = False

        if HAS_YOLO:
            try:
                print("Cargando modelo de Inteligencia Artificial YOLOv8n...")
                self.yolo_model = YOLO("yolov8n.pt")
                self.using_yolo = True
                print("Modelo YOLOv8n cargado exitosamente.")
            except Exception as e:
                print(f"Aviso: No se pudo cargar YOLOv8 ({e}). Usando visión por color/forma.")
                self.using_yolo = False
        else:
            print("Ultralytics no está disponible. Usando detector de visión artificial por color/forma.")

    def detect_hsv_shape(self, frame):
        """Detección por visión computacional clásica."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_orange = np.array([3, 70, 55], dtype="uint8")
        upper_orange = np.array([30, 255, 255], dtype="uint8")
        
        mask = cv2.inRange(hsv, lower_orange, upper_orange)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best_box = None
        best_conf = 0.0
        h_frame, w_frame = frame.shape[:2]
        min_area = (h_frame * w_frame) * 0.005

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue

            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue

            circularity = 4 * np.pi * (area / (perimeter * perimeter))
            if circularity > 0.45:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = float(w) / max(h, 1)
                if 0.60 <= aspect_ratio <= 1.55:
                    conf = min(0.96, 0.45 + (circularity * 0.35) + min(0.2, area / (h_frame * w_frame * 0.1)))
                    if conf > best_conf:
                        best_conf = conf
                        best_box = (x, y, x + w, y + h)

        return best_box, best_conf, "Vision (Color/Forma)"

    def detect(self, frame):
        """Retorna (bbox, conf, engine) donde bbox = (x1, y1, x2, y2)."""
        if self.using_yolo and self.yolo_model is not None:
            try:
                results = self.yolo_model(frame, verbose=False, conf=self.conf_threshold)
                best_box = None
                best_conf = 0.0

                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0].item())
                        conf = float(box.conf[0].item())
                        
                        # 49 = 'orange' en COCO dataset
                        if cls_id == 49:
                            if conf > best_conf:
                                best_conf = conf
                                coords = box.xyxy[0].cpu().numpy().astype(int)
                                best_box = (coords[0], coords[1], coords[2], coords[3])
                        elif cls_id in (47, 32) and conf > 0.45:
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                            x1, y1 = max(0, x1), max(0, y1)
                            x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
                            crop = frame[y1:y2, x1:x2]
                            if crop.size > 0:
                                hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                                orange_mask = cv2.inRange(hsv, (3, 70, 55), (30, 255, 255))
                                orange_ratio = np.count_nonzero(orange_mask) / float(crop.shape[0] * crop.shape[1])
                                if orange_ratio > 0.20 and conf > best_conf:
                                    best_conf = conf
                                    best_box = (x1, y1, x2, y2)

                if best_box is not None:
                    return best_box, best_conf, "IA YOLOv8"
            except Exception:
                pass

        # Motor de respaldo por color y forma
        box, conf, engine = self.detect_hsv_shape(frame)
        if box is not None and conf >= self.conf_threshold:
            return box, conf, engine

        return None, 0.0, None


class OrangeInspectionApp:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.lighting_controller = AutoLightingCamera(camera_index=camera_index) if AutoLightingCamera else None
        self.detector = OrangeDetectorAI()

        # Directorios de almacenamiento
        self.base_dir = "captures"
        self.subdirs = {
            "buen_estado": os.path.join(self.base_dir, "buen_estado"),
            "danadas": os.path.join(self.base_dir, "danadas"),
            "podridas": os.path.join(self.base_dir, "podridas")
        }
        for d in self.subdirs.values():
            os.makedirs(d, exist_ok=True)
        os.makedirs(self.base_dir, exist_ok=True)

        # Archivo CSV de auditoría y registro
        self.csv_path = os.path.join(self.base_dir, "registro_inspeccion.csv")
        self._init_csv()

        # ------------------------------------------------------------------
        # TRACKER DE PERSISTENCIA Y MEMORIA (Evita ráfagas y fotos repetidas)
        # ------------------------------------------------------------------
        # active_object: almacena datos de la naranja actualmente en pantalla
        self.active_object = None
        self.total_oranges_processed = 0

        # Control de presencia/ausencia para transición estricta
        self.present_counter = 0
        self.absent_counter = 0

        # Para considerar que una naranja realmente se fue, debe estar ausente
        # durante al menos 40 fotogramas consecutivos (~1.5 segundos).
        # Esto evita que si se mueve, gira o pasa una mano por delante se tome otra foto!
        self.frames_to_depart = 40
        self.frames_to_confirm_new = 4  # ~0.15s para confirmar entrada antes de disparar

        # Efectos visuales de interfaz
        self.flash_counter = 0
        self.last_saved_info = None
        self.departed_toast_timer = 0.0

    def _init_csv(self):
        """Inicializa el archivo CSV con encabezados si no existe."""
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "ID_Naranja", "Clasificacion", 
                    "Defectos_Pct", "Moho_Pct", "Confianza_IA", "Motor", "Archivo_Foto"
                ])

    def log_to_csv(self, orange_id, classification, defect_pct, mold_pct, conf, engine, filename):
        """Registra cada inspección en el archivo CSV."""
        try:
            with open(self.csv_path, mode="a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    orange_id,
                    classification,
                    f"{defect_pct:.2f}%",
                    f"{mold_pct:.2f}%",
                    f"{conf * 100:.1f}%",
                    engine,
                    filename
                ])
        except Exception as e:
            print(f"Aviso CSV: {e}")

    def play_chime(self):
        """Sonido de obturador en Windows sin bloquear video."""
        if HAS_WINSOUND:
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

    def trigger_capture(self, clean_frame, annotated_frame, bbox, conf, engine, quality_info):
        """Guarda la foto de la naranja clasificada."""
        status, defect_pct, mold_pct, color_bgr, folder_key = quality_info
        
        self.flash_counter = 8
        threading.Thread(target=self.play_chime, daemon=True).start()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_status = folder_key.upper()
        prefix = f"naranja_{self.active_object['id']:03d}_{safe_status}_{timestamp}"

        # Guardar en su carpeta de clasificación y en raíz captures/
        target_folder = self.subdirs[folder_key]
        file_clean_cat = os.path.join(target_folder, f"{prefix}.jpg")
        file_annotated_cat = os.path.join(target_folder, f"{prefix}_analizada.jpg")
        
        file_root_clean = os.path.join(self.base_dir, f"{prefix}.jpg")
        file_root_annotated = os.path.join(self.base_dir, f"{prefix}_analizada.jpg")
        file_latest = os.path.join(self.base_dir, "naranja_ultima_captura.jpg")

        cv2.imwrite(file_clean_cat, clean_frame)
        cv2.imwrite(file_annotated_cat, annotated_frame)
        cv2.imwrite(file_root_clean, clean_frame)
        cv2.imwrite(file_root_annotated, annotated_frame)
        cv2.imwrite(file_latest, annotated_frame)

        # Registrar en CSV
        self.log_to_csv(
            orange_id=self.active_object['id'],
            classification=status,
            defect_pct=defect_pct,
            mold_pct=mold_pct,
            conf=conf,
            engine=engine,
            filename=os.path.basename(file_root_clean)
        )

        self.last_saved_info = {
            "id": self.active_object['id'],
            "status": status,
            "file": os.path.basename(file_root_clean),
            "time": time.time(),
            "color": color_bgr
        }

        print(f"\n=======================================================")
        print(f"  [FOTO CAPTURADA] NUEVA NARANJA #{self.active_object['id']}")
        print(f"  ESTADO: {status}")
        print(f"  DEFECTOS: {defect_pct:.1f}% | MOHO: {mold_pct:.1f}%")
        print(f"  Guardada en: {file_root_clean}")
        print(f"  -> Disparador BLOQUEADO para esta naranja.")
        print(f"     (Retirala de la camara durante 2s para recibir la siguiente)")
        print(f"=======================================================\n")

    def draw_hud(self, display_frame, bbox, conf, engine, quality_info, fps):
        """Dibuja la mira telescópica, información de calidad y estado del tracker."""
        h, w = display_frame.shape[:2]

        # 1. Efecto Flash de Cámara
        if self.flash_counter > 0:
            flash_overlay = display_frame.copy()
            cv2.rectangle(flash_overlay, (0, 0), (w, h), (255, 255, 255), 18)
            cv2.addWeighted(flash_overlay, 0.7, display_frame, 0.3, 0, display_frame)
            self.flash_counter -= 1

        # 2. Bounding Box de la naranja con color de calidad
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            status, defect_pct, mold_pct, color_bgr, _ = quality_info

            thick = 3
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color_bgr, thick)

            # Esquinas destacadas estilo visor moderno
            corner_len = min(25, (x2 - x1) // 4, (y2 - y1) // 4)
            cv2.line(display_frame, (x1, y1), (x1 + corner_len, y1), (255, 255, 255), thick + 1)
            cv2.line(display_frame, (x1, y1), (x1, y1 + corner_len), (255, 255, 255), thick + 1)
            cv2.line(display_frame, (x2, y1), (x2 - corner_len, y1), (255, 255, 255), thick + 1)
            cv2.line(display_frame, (x2, y1), (x2, y1 + corner_len), (255, 255, 255), thick + 1)
            cv2.line(display_frame, (x1, y2), (x1 + corner_len, y2), (255, 255, 255), thick + 1)
            cv2.line(display_frame, (x1, y2), (x1, y2 - corner_len), (255, 255, 255), thick + 1)
            cv2.line(display_frame, (x2, y2), (x2 - corner_len, y2), (255, 255, 255), thick + 1)
            cv2.line(display_frame, (x2, y2), (x2, y2 - corner_len), (255, 255, 255), thick + 1)

            # Etiqueta sobre el objeto con Calidad
            obj_id_str = f"#{self.active_object['id']}" if self.active_object else "NUEVA"
            label = f"NARANJA {obj_id_str}: {status} ({defect_pct:.1f}% def)"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 0.52, 1)
            label_y1 = max(0, y1 - 26)
            cv2.rectangle(display_frame, (x1, label_y1), (x1 + tw + 14, label_y1 + 22), (20, 20, 20), -1)
            cv2.rectangle(display_frame, (x1, label_y1), (x1 + tw + 14, label_y1 + 22), color_bgr, 1)
            cv2.putText(display_frame, label, (x1 + 6, label_y1 + 16), cv2.FONT_HERSHEY_DUPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)

        # 3. Barra superior de estado (HUD)
        overlay = display_frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 55), (15, 15, 15), -1)
        cv2.rectangle(overlay, (0, h - 35), (w, h), (15, 15, 15), -1)
        cv2.addWeighted(overlay, 0.75, display_frame, 0.25, 0, display_frame)

        if self.active_object and self.active_object["photographed"]:
            state_text = f"NARANJA #{self.active_object['id']} REGISTRADA | MEMORIA ACTIVA: NO SE REPETIRA FOTO"
            state_color = (0, 255, 128) # Verde
        elif bbox is not None:
            state_text = "ENFOCANDO Y CALIFICANDO NUEVA NARANJA..."
            state_color = (0, 215, 255) # Amarillo
        else:
            state_text = "ESPERANDO NUEVA NARANJA (Coloca una en la camara)..."
            state_color = (200, 200, 200) # Gris

        cv2.putText(display_frame, state_text, (15, 25), cv2.FONT_HERSHEY_DUPLEX, 0.52, state_color, 1, cv2.LINE_AA)

        # Subtexto de métricas
        sub_metrics = f"Total Inspeccionadas: {self.total_oranges_processed}  |  Iluminacion Auto: ACTIVA  |  {fps:.0f} FPS"
        cv2.putText(display_frame, sub_metrics, (15, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (200, 200, 200), 1, cv2.LINE_AA)

        # Toast banner temporal si la naranja fue retirada
        if time.time() - self.departed_toast_timer < 2.5:
            toast = "[OK] Naranja retirada con exito. Sistema listo para la siguiente naranja!"
            cv2.rectangle(display_frame, (15, 65), (15 + len(toast) * 10, 95), (180, 100, 0), -1)
            cv2.putText(display_frame, toast, (20, 86), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
        elif self.last_saved_info and (time.time() - self.last_saved_info["time"] < 3.5):
            info = self.last_saved_info
            toast = f"FOTO #{info['id']} [{info['status']}] GUARDADA -> {info['file']}"
            cv2.rectangle(display_frame, (15, 65), (15 + len(toast) * 11, 95), (0, 140, 0), -1)
            cv2.putText(display_frame, toast, (20, 87), cv2.FONT_HERSHEY_DUPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)

        # Barra inferior de atajos
        footer = "Inspeccion Automatica: 1 Foto por Naranja -> Retira para la siguiente  |  [C]: Manual  |  [Q]: Salir"
        cv2.putText(display_frame, footer, (15, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1, cv2.LINE_AA)

    def run(self):
        print("=" * 70)
        print("   PackIACamara - INSPECCION DE CALIDAD Y CICLO DE VIDA DE NARANJAS")
        print("=" * 70)
        print("Conectando camara y calibrando sensores...")

        cap = cv2.VideoCapture(self.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        ret, test_frame = cap.read() if cap.isOpened() else (False, None)
        if not ret:
            if cap.isOpened():
                cap.release()
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            ret, test_frame = cap.read() if cap.isOpened() else (False, None)

        if not cap.isOpened() or not ret:
            print(f"Error: No se pudo abrir la camara en el indice {self.camera_index}.")
            print("Verifica que ninguna otra aplicacion tenga bloqueada la camara.")
            return False

        print("\nCamara conectada correctamente.")
        print("Flujo de Operacion:")
        print("  1. Coloca una naranja -> La IA la clasifica (Buen estado, Defecto o Podrida).")
        print("  2. Toma 1 sola foto y BLOQUEA disparos adicionales.")
        print("  3. Puedes moverla o rotarla: el sistema sabe que es la misma naranja.")
        print("  4. Retirala de la camara durante 2 segundos para rearmar.")
        print("  5. Coloca la siguiente naranja -> Se registra como nueva.\n")

        window_name = "PackIACamara - Inspeccion de Calidad de Naranjas"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        prev_time = time.time()
        fps = 30.0

        try:
            while True:
                ret, raw_frame = cap.read()
                if not ret or raw_frame is None:
                    time.sleep(0.05)
                    continue

                now = time.time()
                dt = now - prev_time
                prev_time = now
                if dt > 0:
                    fps = 0.9 * fps + 0.1 * (1.0 / dt)

                # 1. Ajuste adaptativo de iluminación en tiempo real
                if self.lighting_controller:
                    enhanced_frame, _, _ = self.lighting_controller.process_frame(raw_frame)
                else:
                    enhanced_frame = raw_frame.copy()

                # 2. Detección espacial de la naranja
                bbox, conf, engine = self.detector.detect(enhanced_frame)

                # 3. Análisis de calidad superficial si hay detección
                quality_info = ("BUEN ESTADO", 0.0, 0.0, (0, 255, 128), "buen_estado")
                if bbox is not None:
                    x1, y1, x2, y2 = bbox
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(enhanced_frame.shape[1], x2), min(enhanced_frame.shape[0], y2)
                    crop = enhanced_frame[y1:y2, x1:x2]
                    quality_info = OrangeQualityClassifier.classify(crop)

                # 4. GESTIÓN DE MEMORIA Y PERSISTENCIA (Anti-Ráfagas / Anti-Flicker)
                if bbox is not None:
                    self.present_counter += 1
                    self.absent_counter = 0

                    if self.active_object is None:
                        # Si no hay objeto activo y se detecta presencia constante
                        if self.present_counter >= self.frames_to_confirm_new:
                            self.total_oranges_processed += 1
                            self.active_object = {
                                "id": self.total_oranges_processed,
                                "bbox": bbox,
                                "photographed": True,
                                "first_seen": now
                            }
                            # Preparar imagen anotada para guardado
                            annotated = enhanced_frame.copy()
                            self.draw_hud(annotated, bbox, conf, engine, quality_info, fps)
                            self.trigger_capture(enhanced_frame, annotated, bbox, conf, engine, quality_info)
                    else:
                        # Ya tenemos un objeto activo en pantalla:
                        # Actualizar su última posición conocida y MANTENER BLOQUEADO EL DISPARADOR
                        self.active_object["bbox"] = bbox
                        # CERO FOTOS ADICIONALES MIENTRAS ESTE PRESENTE

                else:
                    # No hay detección en este fotograma
                    self.absent_counter += 1
                    self.present_counter = 0

                    if self.active_object is not None:
                        # Solo si pasa ausente más de 40 fotogramas continuos (~1.5 a 2 segundos)
                        # se confirma que el usuario REALMENTE retiró la naranja
                        if self.absent_counter >= self.frames_to_depart:
                            print(f"[-] Naranja #{self.active_object['id']} retirada con exito. Disparador rearmado.")
                            self.active_object = None
                            self.departed_toast_timer = time.time()

                # 5. Renderizar HUD y visualización en tiempo real
                display_frame = enhanced_frame.copy()
                self.draw_hud(display_frame, bbox, conf, engine, quality_info, fps)

                cv2.imshow(window_name, display_frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), ord('Q'), 27):
                    break
                elif key in (ord('c'), ord('C')):
                    # Captura manual
                    self.total_oranges_processed += 1
                    self.active_object = {
                        "id": self.total_oranges_processed,
                        "bbox": bbox or (0, 0, 100, 100),
                        "photographed": True,
                        "first_seen": now
                    }
                    annotated = enhanced_frame.copy()
                    self.draw_hud(annotated, bbox, conf or 1.0, engine or "Manual", quality_info, fps)
                    self.trigger_capture(enhanced_frame, annotated, bbox, conf or 1.0, engine or "Manual", quality_info)

        finally:
            cap.release()
            cv2.destroyAllWindows()
            print("\nInspeccion finalizada.")


if __name__ == "__main__":
    app = OrangeInspectionApp(camera_index=0)
    app.run()
