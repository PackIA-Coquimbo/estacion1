# PackIACamara 📷🤖

Proyecto para adquisición de video, diagnóstico, auto-ajuste de iluminación ambiental y procesamiento de visión artificial (IA).

---

## 📊 Estado Actual: Fase 1 y 2 (Cámara y Ajuste Automático) — ✅ COMPLETADAS

1. **Hardware verificado:** Cámara `Webcam` (USB DirectShow / Media Foundation, Hardware ID `VID_1D6C&PID_1278`).
2. **Ajuste Automático de Iluminación implementado:**
   - **Compensación de Entorno Dinámica:** Ya sea en habitaciones oscuras, con luz tenue, con exceso de luz o con **fuerte contraluz** (como ventanas detrás del objeto), el sistema detecta la iluminación en la región central del objeto y la equilibra automáticamente.
   - **Algoritmo Híbrido:**
     - **CLAHE (Contrast Limited Adaptive Histogram Equalization)** en espacio de color LAB para recuperar detalles en sombras sin quemar las zonas iluminadas.
     - **Corrección Gamma Adaptativa Ponderada:** Centrada en los objetos que están al frente de la cámara con suavizado temporal (evita parpadeos).
     - **Compensación de Color:** Mantiene la vivacidad de los colores al aumentar la exposición en zonas oscuras.
   - **Rendimiento:** Más de 200 FPS de procesamiento por fotograma (latencia imperceptible de ~2.5 ms).

---

## ⚡ Ejecución Rápida con un Doble Clic (`.bat`)

Para activar el modo automático sin necesidad de abrir la consola:

- **`iniciar_camara_auto.bat`** 🚀: Haz doble clic en este archivo en el Explorador de Windows para abrir directamente la cámara con el ajuste automático de iluminación activado.
- **`probar_camara.bat`**: Ejecuta una prueba rápida de diagnóstico y guarda una instantánea en la carpeta `captures/`.

---

## 🎮 Controles en Pantalla (HUD Interactivo)

Cuando la ventana de la cámara esté abierta, puedes usar los siguientes atajos de teclado:

| Tecla | Acción | Descripción |
| :---: | :--- | :--- |
| **`A`** | Alternar Modo Automático | Cambia entre la imagen cruda original y la imagen auto-ajustada. |
| **`S`** | Modo Split-Screen (Comparación) | Divide la pantalla en dos: izquierda original vs derecha mejorada en tiempo real. |
| **`C`** | Capturar Foto | Guarda una foto procesada en la carpeta `captures/`. |
| **`+`** / **`-`** | Calibrar Brillo Objetivo | Aumenta o disminuye el nivel de iluminación deseado si prefieres una imagen más clara u oscura. |
| **`Q`** o **`ESC`** | Salir | Cierra la ventana y libera la cámara de manera limpia. |

---

## 📁 Estructura del Proyecto

```text
PackIACamara/
├── iniciar_camara_auto.bat # Lanzador directo de Windows con modo automático
├── probar_camara.bat        # Lanzador para prueba rápida de diagnóstico
├── auto_camera.py          # Motor de ajuste automático de brillo y contraste
├── test_camera.py          # Script de diagnóstico técnico
├── view_stream.py          # Visualizador simple
├── captures/               # Fotografías de prueba e instantáneas guardadas
├── .venv/                  # Entorno virtual aislado de Python
├── requirements.txt        # Dependencias (opencv-python, numpy, pillow)
└── README.md               # Documentación general del proyecto
```

---

## 🎯 Próximo Paso: Fase 3 (Identificación de Objetos con IA)

Con la cámara funcionando y ajustando la iluminación automáticamente según el entorno, el siguiente paso es conectar el modelo de IA para detectar e identificar los objetos al frente:

1. **Detección de objetos cotidianos/personas** (YOLOv8 / YOLO11 en tiempo real).
2. **Reconocimiento o seguimiento de objetos específicos** según tu necesidad (etiquetas, piezas, productos, cajas, etc.).
3. **Reconocimiento facial o de posturas**.
4. **Lectura de códigos QR / códigos de barras / OCR**.
