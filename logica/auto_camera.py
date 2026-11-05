"""
PackIACamara - Módulo de Cámara con Ajuste Automático de Brillo y Contraste
Adapta dinámicamente la imagen según el entorno (lugares oscuros, contraluz o exceso de luz)
para optimizar la visibilidad de objetos en primer plano.
"""

import cv2
import numpy as np
import time
import os
from datetime import datetime

class AutoLightingCamera:
    def __init__(self, camera_index=0, target_brightness=130.0, smoothing=0.15):
        """
        :param camera_index: Índice de la cámara (por defecto 0).
        :param target_brightness: Nivel de brillo objetivo (0-255). 125-135 es óptimo para visión.
        :param smoothing: Factor de suavizado temporal para transiciones suaves (0.05 a 0.25).
        """
        self.camera_index = camera_index
        self.target_brightness = target_brightness
        self.smoothing = smoothing
        
        # Estado interno
        self.auto_mode = True
        self.split_view = False
        self.current_gamma = 1.0
        self.current_brightness = 100.0
        
        # Filtro adaptativo CLAHE
        self.clahe = cv2.createCLAHE(clipLimit=2.8, tileGridSize=(8, 8))
        
        # Tablas de correspondencia para rendimiento ultra-rápido (LUT)
        self._lut_cache = {}
        
        os.makedirs("captures", exist_ok=True)

    def _get_gamma_lut(self, gamma):
        """Crea o recupera de caché la tabla LUT para corrección gamma rápida."""
        gamma_key = round(gamma, 2)
        if gamma_key not in self._lut_cache:
            inv_gamma = 1.0 / max(gamma_key, 0.05)
            lut = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype("uint8")
            # Mantener caché pequeña
            if len(self._lut_cache) > 100:
                self._lut_cache.clear()
            self._lut_cache[gamma_key] = lut
        return self._lut_cache[gamma_key]

    def measure_brightness(self, frame):
        """
        Calcula el brillo promedio dando mayor ponderación a la región central
        donde suelen situarse los objetos frente a la cámara.
        """
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Región de interés central (60% central)
        y1, y2 = int(h * 0.2), int(h * 0.8)
        x1, x2 = int(w * 0.2), int(w * 0.8)
        center_roi = gray[y1:y2, x1:x2]
        
        center_mean = float(np.mean(center_roi))
        global_mean = float(np.mean(gray))
        
        # 70% peso al centro (objetos al frente), 30% a la escena completa
        weighted_brightness = (0.7 * center_mean) + (0.3 * global_mean)
        return weighted_brightness, center_roi

    def process_frame(self, frame):
        """
        Aplica el pipeline de compensación automática de iluminación:
        1. Medición de brillo ponderado
        2. Compensación local de contraste (CLAHE en espacio LAB)
        3. Suavizado y ajuste adaptativo de gamma
        """
        if not self.auto_mode:
            return frame.copy(), self.current_brightness, self.current_gamma

        # 1. Medir iluminación actual
        measured_brightness, _ = self.measure_brightness(frame)
        self.current_brightness = (1.0 - self.smoothing) * self.current_brightness + (self.smoothing * measured_brightness)
        
        # 2. Calcular gamma objetivo
        # Si la escena está muy oscura (<130), gamma < 1.0 (eleva sombras)
        # Si la escena está sobreexpuesta (>130), gamma > 1.0 (reduce sobreexposición)
        safe_measured = max(self.current_brightness, 10.0)
        target_ratio = np.clip(safe_measured / 255.0, 0.04, 0.96)
        goal_ratio = np.clip(self.target_brightness / 255.0, 0.04, 0.96)
        
        target_gamma = np.log(target_ratio) / np.log(goal_ratio)
        target_gamma = float(np.clip(target_gamma, 0.35, 2.5))
        
        # Suavizar transición para evitar parpadeos
        self.current_gamma = (1.0 - self.smoothing) * self.current_gamma + (self.smoothing * target_gamma)

        # 3. Ecualización adaptativa local en espacio de color LAB
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        enhanced_l = self.clahe.apply(l)
        enhanced_lab = cv2.merge((enhanced_l, a, b))
        local_adjusted = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

        # 4. Aplicación de gamma global optimizada con LUT
        lut = self._get_gamma_lut(self.current_gamma)
        final_frame = cv2.LUT(local_adjusted, lut)

        # 5. Si la corrección aumentó mucho el brillo, compensar levemente la saturación para colores vivos
        if self.current_gamma < 0.8:
            hsv = cv2.cvtColor(final_frame, cv2.COLOR_BGR2HSV)
            h_ch, s_ch, v_ch = cv2.split(hsv)
            s_ch = cv2.multiply(s_ch, 1.15)
            s_ch = np.clip(s_ch, 0, 255).astype("uint8")
            final_frame = cv2.cvtColor(cv2.merge((h_ch, s_ch, v_ch)), cv2.COLOR_HSV2BGR)

        return final_frame, self.current_brightness, self.current_gamma

    def draw_hud(self, display_img, fps):
        """Dibuja información y controles en pantalla con interfaz moderna."""
        h, w = display_img.shape[:2]
        
        # Panel superior semi-transparente
        overlay = display_img.copy()
        cv2.rectangle(overlay, (0, 0), (w, 55), (20, 20, 20), -1)
        cv2.rectangle(overlay, (0, h - 35), (w, h), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.65, display_img, 0.35, 0, display_img)

        # Estado del modo automático
        if self.auto_mode:
            status_text = "MODO AUTO: ACTIVO"
            status_color = (0, 255, 128)  # Verde esmeralda
        else:
            status_text = "MODO AUTO: DESACTIVADO (ORIGINAL)"
            status_color = (0, 165, 255)  # Naranja

        cv2.putText(display_img, status_text, (15, 25), cv2.FONT_HERSHEY_DUPLEX, 0.55, status_color, 1, cv2.LINE_AA)
        
        # Métricas de iluminación y FPS
        metrics_text = f"Brillo Actual: {self.current_brightness:.1f} | Objetivo: {self.target_brightness:.0f} | Gamma: {self.current_gamma:.2f} | {fps:.0f} FPS"
        cv2.putText(display_img, metrics_text, (15, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)

        # Barra de atajos en la parte inferior
        shortcuts = "[A] Alternar Auto  |  [S] Comparar (Split)  |  [C] Capturar  |  [+/-] Brillo Obj.  |  [Q] Salir"
        cv2.putText(display_img, shortcuts, (15, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1, cv2.LINE_AA)

    def run(self):
        """Bucle principal de captura y visualización."""
        print("=" * 60)
        print("  PackIACamara - MODO AUTOMATICO DE ILUMINACION")
        print("=" * 60)
        print("Conectando con la camara...")

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
            print("Aviso: Asegurate de que otra aplicacion (ej. la aplicacion 'Camara' de Windows) no este ocupando el dispositivo.")
            return False
        
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"Camara conectada correctamente ({actual_w}x{actual_h}).")
        print("Iniciando ventana de visualizacion...")
        print("Atajos de teclado:")
        print("  [A]     - Activar/Desactivar ajuste automatico")
        print("  [S]     - Vista dividida (Original vs Ajustado)")
        print("  [C]     - Guardar captura actual en carpeta captures/")
        print("  [+] / [-] - Aumentar / Reducir brillo objetivo")
        print("  [Q] / [ESC] - Salir")

        prev_time = time.time()
        fps = 30.0

        window_name = "PackIACamara - Auto Lighting View"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        try:
            while True:
                ret, raw_frame = cap.read()
                if not ret or raw_frame is None:
                    print("Error al recibir fotograma de la camara.")
                    time.sleep(0.1)
                    continue

                # Calcular FPS instantáneo
                now = time.time()
                dt = now - prev_time
                prev_time = now
                if dt > 0:
                    fps = 0.9 * fps + 0.1 * (1.0 / dt)

                # Procesamiento automático de luz
                enhanced_frame, _, _ = self.process_frame(raw_frame)

                # Composición según modo de vista
                if self.split_view and self.auto_mode:
                    # Dividir la pantalla a la mitad: izquierda original, derecha mejorado
                    h, w = raw_frame.shape[:2]
                    half_w = w // 2
                    split_display = np.hstack((raw_frame[:, :half_w], enhanced_frame[:, half_w:]))
                    # Línea divisoria
                    cv2.line(split_display, (half_w, 0), (half_w, h), (0, 255, 255), 2)
                    cv2.putText(split_display, "ORIGINAL", (half_w - 110, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    cv2.putText(split_display, "AUTO-AJUSTADO", (half_w + 15, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    display_frame = split_display
                elif self.auto_mode:
                    display_frame = enhanced_frame
                else:
                    display_frame = raw_frame.copy()

                # Dibujar interfaz (HUD)
                self.draw_hud(display_frame, fps)

                # Mostrar ventana
                cv2.imshow(window_name, display_frame)

                # Gestión de teclas
                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), ord('Q'), 27):  # Q o ESC
                    break
                elif key in (ord('a'), ord('A')):
                    self.auto_mode = not self.auto_mode
                    print(f"Modo automatico: {'ACTIVADO' if self.auto_mode else 'DESACTIVADO'}")
                elif key in (ord('s'), ord('S')):
                    self.split_view = not self.split_view
                    print(f"Modo split view: {'ACTIVADO' if self.split_view else 'DESACTIVADO'}")
                elif key in (ord('+'), ord('=')):
                    self.target_brightness = min(220.0, self.target_brightness + 10.0)
                    print(f"Brillo objetivo aumentado a: {self.target_brightness:.0f}")
                elif key in (ord('-'), ord('_')):
                    self.target_brightness = max(50.0, self.target_brightness - 10.0)
                    print(f"Brillo objetivo reducido a: {self.target_brightness:.0f}")
                elif key in (ord('c'), ord('C')):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"captures/auto_capture_{timestamp}.jpg"
                    # Guardar la imagen limpia mejorada (sin HUD)
                    cv2.imwrite(filename, enhanced_frame if self.auto_mode else raw_frame)
                    print(f"Captura guardada en: {filename}")

        finally:
            cap.release()
            cv2.destroyAllWindows()
            print("Camara cerrada correctamente.")

if __name__ == "__main__":
    camera = AutoLightingCamera(camera_index=0, target_brightness=130.0)
    camera.run()
