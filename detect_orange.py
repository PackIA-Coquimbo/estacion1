"""
PackIACamara - Detección Inteligente de Naranjas por Ciclo de Vida (Entrada / Foto / Salida)
Detecta cuando una naranja entra en escena, equilibra la iluminación, toma UNA sola fotografía,
bloquea disparos adicionales mientras la naranja permanezca, y detecta cuando se retira
para quedar armada y lista para la siguiente naranja.
"""

import os
import sys
import time
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

# Importar motor de auto-iluminación
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


class OrangeDetectorAI:
    """
    Detector híbrido inteligente para naranjas:
    1. Motor principal: Red Neuronal YOLOv8 (clase 'orange', ID 49 en COCO)
    2. Motor complementario/fallback: Segmentación por color HSV y circularidad
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
        """Detección por visión computacional clásica (color HSV + contorno circular)."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Rango amplio y flexible para cualquier variedad de naranja/mandarina
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
        """Ejecuta la detección sobre el fotograma."""
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
                        # Respaldo si se clasifica como manzana o pelota con tonalidad naranja
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

        # Motor de respaldo por color y geometría
        box, conf, engine = self.detect_hsv_shape(frame)
        if box is not None and conf >= self.conf_threshold:
            return box, conf, engine

        return None, 0.0, None


class OrangeAutoCaptureApp:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.lighting_controller = AutoLightingCamera(camera_index=camera_index) if AutoLightingCamera else None
        self.detector = OrangeDetectorAI()

        self.save_dir = os.path.join("captures", "naranjas")
        os.makedirs(self.save_dir, exist_ok=True)
        os.makedirs("captures", exist_ok=True)

        # ----------------------------------------------------
        # MÁQUINA DE ESTADOS DE CICLO DE VIDA (1 FOTO POR OBJETO)
        # ----------------------------------------------------
        # Estados: 'ESPERANDO' -> 'CONFIRMANDO' -> 'REGISTRADA' -> 'RETIRADA'
        self.state = "ESPERANDO"
        self.total_oranges_processed = 0
        self.current_orange_id = 0
        
        self.consecutive_present = 0
        self.consecutive_absent = 0
        
        self.min_frames_to_confirm = 3   # Fotogramas seguidos para confirmar entrada (~0.1s)
        self.min_frames_to_depart = 8    # Fotogramas seguidos sin naranja para confirmar salida (~0.3s)
        
        # Efectos visuales y de sonido
        self.flash_counter = 0
        self.last_saved_info = None
        self.departed_banner_timer = 0.0

    def play_chime(self):
        """Reproduce un sonido de obturador en Windows sin bloquear el video."""
        if HAS_WINSOUND:
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

    def trigger_auto_capture(self, clean_frame, annotated_frame, bbox, conf, engine):
        """Guarda la foto de la nueva naranja identificada."""
        self.flash_counter = 8  # Duración del flash visual (fotogramas)
        threading.Thread(target=self.play_chime, daemon=True).start()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"naranja_{self.current_orange_id:03d}_{timestamp}"
        
        # Guardar en captures/ y en captures/naranjas/
        file_clean_root = os.path.join("captures", f"{prefix}.jpg")
        file_annotated_root = os.path.join("captures", f"{prefix}_detectada.jpg")
        file_latest_root = os.path.join("captures", "naranja_ultima_captura.jpg")
        
        filename_clean = os.path.join(self.save_dir, f"{prefix}.jpg")
        filename_annotated = os.path.join(self.save_dir, f"{prefix}_detectada.jpg")

        cv2.imwrite(file_clean_root, clean_frame)
        cv2.imwrite(file_annotated_root, annotated_frame)
        cv2.imwrite(file_latest_root, annotated_frame)
        cv2.imwrite(filename_clean, clean_frame)
        cv2.imwrite(filename_annotated, annotated_frame)

        self.last_saved_info = {
            "id": self.current_orange_id,
            "file": os.path.basename(file_clean_root),
            "time": time.time(),
            "conf": conf,
            "engine": engine
        }
        print(f"\n[+] NUEVA NARANJA #{self.current_orange_id} IDENTIFICADA ({conf*100:.1f}%) con {engine}!")
        print(f"    Foto guardada: {file_clean_root}")
        print(f"    -> Disparador BLOQUEADO para esta naranja. Retirala para registrar la siguiente.\n")

    def draw_ui(self, display_frame, bbox, conf, engine, fps):
        """Dibuja la interfaz completa, HUD de estado de ciclo de vida y métricas."""
        h, w = display_frame.shape[:2]

        # 1. Flash blanco al tomar foto
        if self.flash_counter > 0:
            flash_overlay = display_frame.copy()
            cv2.rectangle(flash_overlay, (0, 0), (w, h), (255, 255, 255), 18)
            cv2.addWeighted(flash_overlay, 0.7, display_frame, 0.3, 0, display_frame)
            self.flash_counter -= 1

        # 2. Caja de detección
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            if self.state == "REGISTRADA":
                box_color = (0, 255, 128)  # Verde: Ya registrada
                status_tag = f"NARANJA #{self.current_orange_id} [REGISTRADA]"
            else:
                box_color = (0, 165, 255)  # Naranja: Identificando
                status_tag = f"NARANJA: {conf*100:.0f}% [{engine}]"

            thick = 3
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), box_color, thick)

            # Esquinas destacadas estilo visor moderno
            corner_len = min(25, (x2 - x1) // 4, (y2 - y1) // 4)
            cv2.line(display_frame, (x1, y1), (x1 + corner_len, y1), (0, 255, 255), thick + 1)
            cv2.line(display_frame, (x1, y1), (x1, y1 + corner_len), (0, 255, 255), thick + 1)
            cv2.line(display_frame, (x2, y1), (x2 - corner_len, y1), (0, 255, 255), thick + 1)
            cv2.line(display_frame, (x2, y1), (x2, y1 + corner_len), (0, 255, 255), thick + 1)
            cv2.line(display_frame, (x1, y2), (x1 + corner_len, y2), (0, 255, 255), thick + 1)
            cv2.line(display_frame, (x1, y2), (x1, y2 - corner_len), (0, 255, 255), thick + 1)
            cv2.line(display_frame, (x2, y2), (x2 - corner_len, y2), (0, 255, 255), thick + 1)
            cv2.line(display_frame, (x2, y2), (x2, y2 - corner_len), (0, 255, 255), thick + 1)

            # Etiqueta
            (tw, th), _ = cv2.getTextSize(status_tag, cv2.FONT_HERSHEY_DUPLEX, 0.55, 1)
            label_y1 = max(0, y1 - 28)
            cv2.rectangle(display_frame, (x1, label_y1), (x1 + tw + 16, label_y1 + 24), (20, 20, 20), -1)
            cv2.rectangle(display_frame, (x1, label_y1), (x1 + tw + 16, label_y1 + 24), box_color, 1)
            cv2.putText(display_frame, status_tag, (x1 + 8, label_y1 + 17), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        # 3. Panel superior HUD semi-transparente
        overlay = display_frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 55), (20, 20, 20), -1)
        cv2.rectangle(overlay, (0, h - 35), (w, h), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.70, display_frame, 0.30, 0, display_frame)

        # Estado del ciclo de vida en texto claro
        if self.state == "REGISTRADA":
            state_text = f"ESTADO: NARANJA #{self.current_orange_id} REGISTRADA (Retirala para la siguiente)"
            state_color = (0, 255, 128)  # Verde
        elif self.state == "CONFIRMANDO":
            state_text = "ESTADO: IDENTIFICANDO Y ENFOCANDO NUEVA NARANJA..."
            state_color = (0, 215, 255)  # Amarillo/Naranja
        else:
            state_text = "ESTADO: ESPERANDO NUEVA NARANJA (Coloca una frente a la camara)..."
            state_color = (200, 200, 200)  # Gris claro

        cv2.putText(display_frame, state_text, (15, 25), cv2.FONT_HERSHEY_DUPLEX, 0.53, state_color, 1, cv2.LINE_AA)

        # Subtexto con contador total y métricas
        sub_info = f"Total Procesadas: {self.total_oranges_processed}  |  Iluminacion Auto: ACTIVA  |  {fps:.0f} FPS"
        cv2.putText(display_frame, sub_info, (15, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (200, 200, 200), 1, cv2.LINE_AA)

        # Notificación temporal cuando se retira la naranja
        if time.time() - self.departed_banner_timer < 2.0:
            msg = "[OK] Naranja retirada con exito. Listo para recibir la siguiente!"
            cv2.rectangle(display_frame, (15, 65), (15 + len(msg) * 10, 95), (180, 100, 0), -1)
            cv2.putText(display_frame, msg, (20, 86), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1, cv2.LINE_AA)
        elif self.last_saved_info and (time.time() - self.last_saved_info["time"] < 3.0):
            banner_text = f"FOTO TOMADA -> {self.last_saved_info['file']} (No se repetira)"
            cv2.rectangle(display_frame, (15, 65), (15 + len(banner_text) * 11, 95), (0, 140, 0), -1)
            cv2.putText(display_frame, banner_text, (20, 87), cv2.FONT_HERSHEY_DUPLEX, 0.50, (255, 255, 255), 1, cv2.LINE_AA)

        # Barra inferior de controles
        footer = "Ciclo Inteligente: 1 Foto por Naranja -> Retira para la Siguiente  |  [C]: Manual  |  [Q]: Salir"
        cv2.putText(display_frame, footer, (15, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1, cv2.LINE_AA)

    def run(self):
        print("=" * 65)
        print("  PackIACamara - DETECCION INTELIGENTE POR CICLO DE VIDA")
        print("=" * 65)
        print("Iniciando camara y calibrando entorno...")

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
            print(f"Error: No se pudo obtener senal de la camara en el indice {self.camera_index}.")
            print("Aviso: Asegurate de que ninguna otra aplicacion tenga bloqueada la camara.")
            return False

        print("\nCamara conectada correctamente.")
        print("Modo de Operacion Inteligente:")
        print("  1. Coloca una naranja -> La detecta, toma 1 foto y la bloquea.")
        print("  2. Mientras la naranja este ahi -> NO se tomaran mas fotos.")
        print("  3. Retira la naranja -> El sistema detecta que se fue y se rearma.")
        print("  4. Coloca una nueva naranja -> Toma foto de la nueva y cuenta +1.\n")

        window_name = "PackIACamara - Detector de Naranjas por Ciclo de Vida"
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

                # 1. Ajuste adaptativo de luz
                if self.lighting_controller:
                    enhanced_frame, _, _ = self.lighting_controller.process_frame(raw_frame)
                else:
                    enhanced_frame = raw_frame.copy()

                # 2. Detección de naranja
                bbox, conf, engine = self.detector.detect(enhanced_frame)

                # 3. LÓGICA DE ESTADOS (1 FOTO POR OBJETO HASTA QUE SE VAYA)
                if bbox is not None:
                    self.consecutive_present += 1
                    self.consecutive_absent = 0

                    if self.state == "ESPERANDO":
                        if self.consecutive_present >= self.min_frames_to_confirm:
                            # ¡NUEVA NARANJA CONFIRMADA!
                            self.total_oranges_processed += 1
                            self.current_orange_id = self.total_oranges_processed
                            self.state = "REGISTRADA"

                            # Tomar foto de esta nueva naranja
                            annotated = enhanced_frame.copy()
                            self.draw_ui(annotated, bbox, conf, engine, fps)
                            self.trigger_auto_capture(enhanced_frame, annotated, bbox, conf, engine)
                        else:
                            self.state = "CONFIRMANDO"

                    elif self.state == "REGISTRADA":
                        # La naranja SIGUE en escena -> CERO fotos adicionales
                        pass

                else:
                    self.consecutive_absent += 1
                    self.consecutive_present = 0

                    if self.state in ("REGISTRADA", "CONFIRMANDO"):
                        if self.consecutive_absent >= self.min_frames_to_depart:
                            # ¡LA NARANJA SE HA IDO!
                            print(f"[-] Naranja #{self.current_orange_id} retirada del plano. Listo para la siguiente.")
                            self.state = "ESPERANDO"
                            self.departed_banner_timer = time.time()

                # 4. Renderizar pantalla
                display_frame = enhanced_frame.copy()
                self.draw_ui(display_frame, bbox, conf, engine, fps)

                cv2.imshow(window_name, display_frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), ord('Q'), 27):
                    break
                elif key in (ord('c'), ord('C')):
                    # Captura manual
                    self.total_oranges_processed += 1
                    self.current_orange_id = self.total_oranges_processed
                    self.state = "REGISTRADA"
                    annotated = enhanced_frame.copy()
                    self.draw_ui(annotated, bbox, conf or 1.0, engine or "Manual", fps)
                    self.trigger_auto_capture(enhanced_frame, annotated, bbox, conf or 1.0, engine or "Manual")

        finally:
            cap.release()
            cv2.destroyAllWindows()
            print("\nDetector finalizado limpiamente.")


if __name__ == "__main__":
    app = OrangeAutoCaptureApp(camera_index=0)
    app.run()
