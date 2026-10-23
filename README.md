# PackIACamara 📷🤖

Sistema inteligente de visión por computador con auto-calibración de iluminación, detección de objetos mediante Inteligencia Artificial (YOLOv8) y captura fotográfica automatizada.

---

## 📊 Estado Actual: Fase 1, 2 y 3 — ✅ COMPLETADAS

1. **Hardware verificado:** Cámara `Webcam` (DirectShow / Media Foundation, Hardware ID `VID_1D6C&PID_1278`).
2. **Ajuste Automático de Iluminación:**
   - Algoritmo híbrido CLAHE (espacio LAB) + Gamma dinámico ponderado por objeto central.
   - Corrige sombras, contraluz (ventanas) o exceso de luz a más de 200 FPS.
3. **Detección de Objetos y Auto-Captura (Prueba: Naranja 🍊):**
   - **Motor Dual:** Red Neuronal **YOLOv8n** (clase `orange` COCO #49) con respaldo de visión por color HSV y circularidad.
   - **Disparador Inteligente:** Al identificar una naranja de manera estable (evitando falsos positivos):
     - Produce un **efecto visual de flash** en la pantalla.
     - Reproduce un **sonido de obturador** en Windows.
     - Guarda automáticamente **2 fotografías en `captures/naranjas/`**:
       1. `naranja_YYYYMMDD_HHMMSS.jpg`: Fotografía limpia en alta resolución con iluminación optimizada.
       2. `naranja_YYYYMMDD_HHMMSS_detectada.jpg`: Fotografía con la mira/bounding box, porcentaje de confianza y datos del modelo.
     - Aplica un tiempo de enfriamiento (cooldown) de 3.5 segundos para no saturar con fotos repetidas.

---

## ⚡ Lanzadores Rápidos con un Doble Clic (`.bat`)

En el Explorador de Windows, solo haz doble clic en el archivo que desees:

| Archivo | Función |
| :--- | :--- |
| **`iniciar_detector_naranja.bat`** 🍊📸 | **Inicia el detector de naranjas con auto-iluminación y captura automática de fotos.** |
| **`iniciar_camara_auto.bat`** 💡 | Inicia la cámara solo con el ajuste automático de iluminación ambiental (sin detección). |
| **`probar_camara.bat`** 🔍 | Realiza un diagnóstico rápido del sensor y captura una instantánea de prueba. |

---

## 🎮 Controles en Pantalla (HUD Interactivo)

Durante la ejecución del detector de naranjas:

- **Detección automática:** Solo coloca una naranja frente a la cámara; el recuadro naranja se fijará sobre ella y tomará la foto automáticamente.
- **`C`**: Forzar captura manual en cualquier instante.
- **`Q`** o **`ESC`**: Cerrar y salir de la aplicación.

---

## 📁 Estructura del Repositorio

```text
PackIACamara/
├── iniciar_detector_naranja.bat # Lanzador: Detector IA de naranjas + Auto-Foto
├── iniciar_camara_auto.bat       # Lanzador: Modo auto-iluminación
├── probar_camara.bat             # Lanzador: Test rápido de hardware
├── detect_orange.py             # Módulo principal: Detección IA + Captura
├── auto_camera.py               # Motor de balance adaptativo de iluminación
├── test_camera.py               # Script de comprobación inicial
├── view_stream.py               # Visualizador básico
├── yolov8n.pt                   # Pesos pre-entrenados del modelo YOLOv8n
├── captures/                    # Directorio de instantáneas
│   └── naranjas/                # Fotos capturadas automáticamente de la naranja
├── requirements.txt             # Dependencias (opencv, numpy, pillow, ultralytics)
└── README.md                    # Documentación y bitácora del proyecto
```

---

## 🚀 Próximos Pasos Posibles

- Ampliar la lista de objetos a detectar (botellas, herramientas, cajas, personas, etc.).
- Conectar una base de datos o API para enviar la foto automáticamente cuando se detecte el objeto.
- Activar conteo de objetos o control de calidad visual.
