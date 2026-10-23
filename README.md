# PackIACamara 📷🤖

Sistema inteligente de visión por computador con auto-calibración de iluminación, detección de objetos por Inteligencia Artificial (YOLOv8) y **captura fotográfica automatizada por ciclo de vida (1 foto por objeto)**.

---

## 📊 Estado Actual: Ciclo de Vida y Detección de Entrada / Salida — ✅ IMPLEMENTADO

El sistema ahora opera mediante una **Máquina de Estados de Ciclo de Vida**:

```text
[ESPERANDO] 
    │
    ▼ (Colocas una naranja frente a la cámara)
[NUEVA NARANJA DETECTADA]
    │  - Calibra iluminación
    │  - Dispara flash visual y sonido de obturador
    │  - Guarda 1 sola fotografía (naranja_001_...)
    ▼
[NARANJA REGISTRADA (BLOQUEADA)]
    │  - Mientras la naranja permanezca en escena: CERO FOTOS ADICIONALES
    │
    ▼ (Retiras la naranja del plano)
[DETECCIÓN DE SALIDA]
    │  - El sistema detecta que el objeto se fue
    ▼
[REARMADO AUTOMÁTICO] ──> Listo para recibir la Naranja #002
```

### Características Principales:
1. **Sin ráfagas repetidas**: Cada naranja recibe exactamente **1 fotografía**.
2. **Detección de Retiro/Salida**: Detecta automáticamente cuando se quita la naranja del plano y se prepara para el siguiente objeto.
3. **Contador Progresivo**: Etiqueta y enumera cada naranja de forma ordenada:
   - `captures/naranja_001_YYYYMMDD_HHMMSS.jpg`
   - `captures/naranja_001_YYYYMMDD_HHMMSS_detectada.jpg`
   - `captures/naranja_002_...`
4. **Auto-Ajuste de Iluminación Activo**: Corrige contraluz, sombras y sobreexposición en tiempo real a 30 FPS.

---

## ⚡ Lanzadores Rápidos con un Doble Clic (`.bat`)

| Archivo | Función |
| :--- | :--- |
| **`iniciar_detector_naranja.bat`** 🍊📸 | **Inicia el detector inteligente: 1 foto por naranja, detecta cuando se retira y espera la siguiente.** |
| **`iniciar_camara_auto.bat`** 💡 | Inicia la cámara únicamente con el balance adaptativo de iluminación ambiental. |
| **`probar_camara.bat`** 🔍 | Diagnóstico técnico rápido del sensor. |

---

## 🎮 Controles en Pantalla (HUD)

- **Automático:** Simplemente coloca una naranja -> Se toma 1 foto -> Retírala -> Coloca la siguiente.
- **`C`**: Forzar foto manual si lo deseas.
- **`Q`** o **`ESC`**: Salir y cerrar la aplicación limpiamente.

---

## 📁 Estructura del Repositorio

```text
PackIACamara/
├── iniciar_detector_naranja.bat # Lanzador: Detector con ciclo de vida (1 foto por objeto)
├── iniciar_camara_auto.bat       # Lanzador: Auto-iluminación
├── probar_camara.bat             # Lanzador: Diagnóstico
├── detect_orange.py             # Motor de detección IA + Ciclo de vida (Entrada/Foto/Salida)
├── auto_camera.py               # Motor de balance adaptativo de iluminación
├── yolov8n.pt                   # Pesos del modelo YOLOv8n
├── captures/                    # Fotos organizadas numeradas (_001, _002...)
│   └── naranjas/                # Copia de respaldo
├── requirements.txt             # Dependencias (opencv<5, numpy, pillow, ultralytics)
└── README.md                    # Bitácora del proyecto
```
