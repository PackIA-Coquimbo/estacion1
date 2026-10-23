"""
PackIACamara - Detección Automática de Naranja y Captura Fotográfica Inteligente
Detecta cuando se coloca una naranja frente a la cámara (usando IA YOLOv8 + visión por computador),
y toma una fotografía automáticamente con ajuste adaptativo de iluminación.
"""

import os
import sys
import time
import threading
from datetime import datetime
import cv2
import numpy as np

# Intentar importar winsound en Windows para feedback sonoro
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# Importar el motor de iluminación adaptativa del proyecto
try:
    from auto_camera import AutoLightingCamera
except ImportError:
    AutoLightingCamera = None

# Intentar importar Ultralytics YOLO
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
                print(f"Aviso: No se pudo cargar YOLOv8 ({e}). Usando detector de visión por color/forma.")
                self.using_yolo = False
        else:
            print("Ultralytics no está disponible. Usando detector de visión artificial por color/forma.")

    def detect_hsv_shape(self, frame):
        """
        Detección por visión computacional clásica:
        Rango de tono naranja en HSV + análisis de contornos y circularidad.
        """
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
        min_area = (h_frame * w_frame) * 0.005  # Mínimo tamaño relativo

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue

            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue

            circularity = 4 * np.pi * (area / (perimeter * perimeter))
            
            # Una naranja es aproximadamente circular
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
        """
        Ejecuta la detección sobre el fotograma y retorna:
        (bbox, confianza, etiqueta_motor) o (None, 0.0, None)
        bbox en formato (x1, y1, x2, y2)
        """
        # 1. Intentar con YOLO si está habilitado
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
                        # Respaldo por si el clasificador la etiqueta como manzana o pelota de deportes
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

        # 2. Motor de visión por color y forma (respaldo robusto)
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

        # Parámetros del disparador automático
        self.consecutive_detections = 0
        self.min_consecutive_needed = 3   # ~0.10s continuo para disparo ágil
        self.last_capture_time = 0.0
        self.cooldown_seconds = 3.5       # Espera entre fotos automáticas consecutivas
        
        # Efecto visual de flash
        self.flash_counter = 0
        self.last_saved_info = None

    def play_chime(self):
        """Reproduce un sonido de obturador/confirmación en Windows sin bloquear el video."""
        if HAS_WINSOUND:
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

    def trigger_auto_capture(self, clean_frame, annotated_frame, bbox, conf, engine):
        """Guarda la foto en captures/ y en captures/naranjas/ y activa el efecto de captura."""
        now = time.time()
        self.last_capture_time = now
        self.flash_counter = 8  # Duración del flash visual (en fotogramas)

        # Reproducir sonido en hilo separado
        threading.Thread(target=self.play_chime, daemon=True).start()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Guardar en captures/ (raíz) y en captures/naranjas/
        file_clean_root = os.path.join("captures", f"naranja_{timestamp}.jpg")
        file_annotated_root = os.path.join("captures", f"naranja_{timestamp}_detectada.jpg")
        file_latest_root = os.path.join("captures", "naranja_ultima_captura.jpg")
        
        filename_clean = os.path.join(self.save_dir, f"naranja_{timestamp}.jpg")
        filename_annotated = os.path.join(self.save_dir, f"naranja_{timestamp}_detectada.jpg")

        cv2.imwrite(file_clean_root, clean_frame)
        cv2.imwrite(file_annotated_root, annotated_frame)
        cv2.imwrite(file_latest_root, annotated_frame)
        cv2.imwrite(filename_clean, clean_frame)
        cv2.imwrite(filename_annotated, annotated_frame)

        self.last_saved_info = {
            "file": os.path.basename(file_clean_root),
            "time": time.time(),
            "conf": conf,
            "engine": engine
        }
        print(f"\n>>> [FOTO CAPTURADA EXITOSAMENTE] Naranja identificada ({conf*100:.1f}%) con {engine}!")
        print(f"    Guardada en: {file_clean_root}")
        print(f"    Guardada en: {file_annotated_root}")

    def draw_ui(self, display_frame, bbox, conf, engine, fps):
        """Dibuja la mira telescópica de detección, información de IA y notificaciones."""
        h, w = display_frame.shape[:2]

        # 1. Efecto Flash de Cámara cuando se toma una foto
        if self.flash_counter > 0:
            flash_intensity = min(255, self.flash_counter * 30)
            flash_overlay = display_frame.copy()
            # Borde blanco brillante
            cv2.rectangle(flash_overlay, (0, 0), (w, h), (255, 255, 255), 18)
            cv2.addWeighted(flash_overlay, 0.7, display_frame, 0.3, 0, display_frame)
            self.flash_counter -= 1

        # 2. Caja delimitadora (Bounding Box) si se detecta naranja
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            # Color naranja brillante con marco dinámico
            box_color = (0, 165, 255)  # Naranja BGR
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

            # Etiqueta con porcentaje de confianza y motor
            label = f"NARANJA: {conf * 100:.1f}% [{engine}]"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 0.55, 1)
            label_y1 = max(0, y1 - 28)
            cv2.rectangle(display_frame, (x1, label_y1), (x1 + tw + 16, label_y1 + 24), (20, 20, 20), -1)
            cv2.rectangle(display_frame, (x1, label_y1), (x1 + tw + 16, label_y1 + 24), box_color, 1)
            cv2.putText(display_frame, label, (x1 + 8, label_y1 + 17), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

        # 3. Barra superior de estado
        overlay = display_frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 55), (20, 20, 20), -1)
        cv2.rectangle(overlay, (0, h - 35), (w, h), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.70, display_frame, 0.30, 0, display_frame)

        if bbox is not None:
            state_text = f"OBJETO IDENTIFICADO: NARANJA ({conf*100:.0f}%)"
            state_color = (0, 215, 255)
        else:
            state_text = "BUSCANDO OBJETO (Coloca una naranja frente a la camara)..."
            state_color = (180, 180, 180)

        cv2.putText(display_frame, state_text, (15, 25), cv2.FONT_HERSHEY_DUPLEX, 0.55, state_color, 1, cv2.LINE_AA)
        
        # Subtexto con motor de IA y auto-iluminación
        sub_info = f"IA: {engine if engine else 'Esperando'} | Iluminacion Auto: ACTIVA | {fps:.0f} FPS"
        cv2.putText(display_frame, sub_info, (15, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

        # Banner de confirmación de última foto tomada
        if self.last_saved_info and (time.time() - self.last_saved_info["time"] < 3.0):
            banner_text = f"CAMARA: FOTO GUARDADA -> {self.last_saved_info['file']}"
            cv2.rectangle(display_frame, (15, 65), (15 + len(banner_text) * 11, 95), (0, 140, 0), -1)
            cv2.putText(display_frame, banner_text, (20, 87), cv2.FONT_HERSHEY_DUPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)

        # Barra inferior de controles
        footer = "[Auto-Foto]: ACTIVO al detectar  |  [C]: Foto manual  |  [Q/ESC]: Salir"
        cv2.putText(display_frame, footer, (15, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1, cv2.LINE_AA)

    def run(self):
        print("=" * 65)
        print("    PackIACamara - DETECCION Y CAPTURA AUTOMATICA DE NARANJA")
        print("=" * 65)
        print("Iniciando camara y calibrando entorno...")

        cap = cv2.VideoCapture(self.camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        ret, test_frame = cap.read() if cap.isOpened() else (False, None)
        if not ret:
            if cap.isOpened():
                cap.release()
            # Intento con backend alternativo DirectShow
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            ret, test_frame = cap.read() if cap.isOpened() else (False, None)

        if not cap.isOpened() or not ret:
            print(f"Error: No se pudo obtener senal de la camara en el indice {self.camera_index}.")
            print("Aviso: Asegurate de que ninguna otra aplicacion (como la app 'Camara' de Windows o Zoom/Teams) tenga bloqueada la camara.")
            return False

        print("\nCamara lista.")
        print("Instrucciones:")
        print("  - Coloca una naranja en el campo de vision de la camara.")
        print("  - El sistema ajustara la luz automaticamente y detectara la naranja.")
        print("  - Tomara una fotografia y la guardara en: captures/naranjas/")
        print("  - Presiona 'q' o 'ESC' para salir.\n")

        window_name = "PackIACamara - Detector de Naranjas con Auto-Captura"
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

                # 1. Ajuste adaptativo de iluminacion (siempre optimo)
                if self.lighting_controller:
                    enhanced_frame, _, _ = self.lighting_controller.process_frame(raw_frame)
                else:
                    enhanced_frame = raw_frame.copy()

                # 2. Deteccion de Naranja
                bbox, conf, engine = self.detector.detect(enhanced_frame)

                # 3. Logica de Auto-Captura
                if bbox is not None:
                    self.consecutive_detections += 1
                    # Si la naranja se mantiene estable y no estamos en cooldown
                    if self.consecutive_detections >= self.min_consecutive_needed:
                        if (now - self.last_capture_time) > self.cooldown_seconds:
                            # Preparar imagen anotada
                            annotated = enhanced_frame.copy()
                            self.draw_ui(annotated, bbox, conf, engine, fps)
                            self.trigger_auto_capture(enhanced_frame, annotated, bbox, conf, engine)
                else:
                    self.consecutive_detections = max(0, self.consecutive_detections - 1)

                # 4. Renderizar Interfaz en Pantalla
                display_frame = enhanced_frame.copy()
                self.draw_ui(display_frame, bbox, conf, engine, fps)

                cv2.imshow(window_name, display_frame)

                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), ord('Q'), 27):
                    break
                elif key in (ord('c'), ord('C')):
                    # Captura manual
                    annotated = enhanced_frame.copy()
                    self.draw_ui(annotated, bbox, conf, engine, fps)
                    self.trigger_auto_capture(enhanced_frame, annotated, bbox, conf or 1.0, engine or "Manual")

        finally:
            cap.release()
            cv2.destroyAllWindows()
            print("\nDetector finalizado correctamente.")


if __name__ == "__main__":
    app = OrangeAutoCaptureApp(camera_index=0)
    app.run()
