# PackIACamara 📷🍊🤖

Sistema inteligente de inspección de calidad para cítricos mediante visión por computador (OpenCV), Inteligencia Artificial (YOLOv8) y calibración adaptativa de iluminación en tiempo real.

---

## 🌟 Nuevas Funcionalidades: Control de Calidad y Memoria Persistente

### 1. 🛡️ Memoria de Identidad (Anti-Ráfagas / Sin Fotos Repetidas)
- **1 Sola Foto por Naranja:** Al ingresar una nueva naranja, el sistema enfoca, equilibra la luz y toma **una sola fotografía**.
- **Persistencia Espacio-Temporal:** Puedes **girar la naranja, moverla en la mesa o acomodarla** con la mano; el sistema sabe que sigue siendo la misma naranja y **NO sacará más fotos**.
- **Tiempo de Gracia de Salida (1.5 - 2.0 s):** Para considerar que la naranja fue retirada y preparar la siguiente, el plano debe quedar libre por al menos 40 fotogramas continuos (~2 segundos). Esto evita falsos disparos por parpadeos o movimientos rápidos.

---

### 2. 🔬 Clasificación Automática de Calidad (Buen Estado / Dañadas / Podridas)
El módulo analiza la superficie de la fruta en tiempo real combinando espacios de color **HSV** y **LAB**:

| Estado | Color HUD | Criterio de Inspección | Destino de Guardado |
| :--- | :---: | :--- | :--- |
| **BUEN ESTADO** | 🟢 Verde | Piel limpia, color uniforme y sin manchas (< 5.5% defectos). | `captures/buen_estado/` |
| **DEFECTO LEVE** | 🟡 Amarillo | Golpes superficiales, decoloración o manchas leves (5.5% - 14%). | `captures/danadas/` |
| **PODRIDA / MAL ESTADO** | 🔴 Rojo | Presencia de moho fúngico (*Penicillium*) o necrosis oscura (> 14%). | `captures/podridas/` |

---

### 3. 📊 Auditoría y Reporte Automático en CSV
Cada naranja fotografiada se registra automáticamente en:
📁 **`captures/registro_inspeccion.csv`** con:
- Fecha y Hora exacta
- ID consecutivo (`#1`, `#2`, `#3`...)
- Clasificación de calidad
- Porcentaje de defectos y moho detectado
- Confianza del modelo de IA
- Nombre del archivo de fotografía guardado

---

## ⚡ Cómo Ejecutar con un Doble Clic (`.bat`)

En el Explorador de Windows:

- **`iniciar_detector_naranja.bat`** 🍊🚀: Abre la ventana de inspección en video a 30 FPS con clasificación de calidad y memoria inteligente.
- **`iniciar_camara_auto.bat`** 💡: Abre únicamente el ajuste automático de iluminación ambiental (sin clasificación).
- **`probar_camara.bat`** 🔍: Test rápido de hardware y diagnóstico.

---

## 🎮 Controles en Pantalla (HUD)

- **Flujo Automático:**
  1. Coloca la naranja -> Toma 1 foto clasificada.
  2. Muévela o examínala libremente (no se repetirán fotos).
  3. Retírala por 2 segundos de la cámara -> Se rearma el sensor.
  4. Coloca la siguiente naranja -> Se registra como nueva.
- **`C`**: Forzar foto manual si lo deseas.
- **`Q`** o **`ESC`**: Cerrar y salir de la aplicación.

---

## 📁 Estructura del Repositorio

```text
PackIACamara/
├── iniciar_detector_naranja.bat # Lanzador: Inspección de calidad + Memoria persistente
├── iniciar_camara_auto.bat       # Lanzador: Auto-iluminación
├── probar_camara.bat             # Lanzador: Test diagnóstico
├── detect_orange.py             # Motor de IA, seguimiento espacial y calidad
├── auto_camera.py               # Motor de balance adaptativo de iluminación
├── yolov8n.pt                   # Pesos del modelo YOLOv8
├── captures/                    # Carpeta principal de fotos
│   ├── buen_estado/             # Fotos clasificadas como óptimas
│   ├── danadas/                 # Fotos clasificadas con defectos leves
│   ├── podridas/                # Fotos clasificadas con pudrición / moho
│   └── registro_inspeccion.csv  # Reporte de auditoría y estadísticas
├── requirements.txt             # Dependencias (opencv<5, numpy, pillow, ultralytics)
└── README.md                    # Documentación del proyecto
```
