# PackIACamara 📷🤖

Proyecto para adquisición de video, diagnóstico y procesamiento de visión artificial (IA) con cámara web.

---

## 📊 Estado Actual: Fase 1 (Verificación de Cámara) — ✅ COMPLETADA

La cámara ha sido detectada, inicializada y probada con éxito.

### Diagnóstico de Hardware y Señal
- **Dispositivo:** `Webcam` (PnP / USB `VID_1D6C&PID_1278`)
- **Estado de enlace:** `OK` (Índice de captura: `0`)
- **Resoluciones comprobadas:**
  - `640 x 480` (SD)
  - `1280 x 720` (HD 720p)
  - `1920 x 1080` (Full HD 1080p)
- **Captura de prueba:** Verificada exitosamente en `captures/test_camera_0.jpg`. Los sensores de luminosidad y contraste responden correctamente.

---

## 📁 Estructura del Repositorio

```text
PackIACamara/
├── captures/               # Capturas generadas en pruebas de diagnóstico
│   └── test_camera_0.jpg   # Fotograma de prueba capturado
├── .venv/                  # Entorno virtual de Python aislado
├── .gitignore              # Configuración de exclusiones de Git
├── requirements.txt        # Librerías base (OpenCV, Pillow, NumPy)
├── test_camera.py          # Script automático de diagnóstico y verificación
├── view_stream.py          # Visualizador interactivo de video en tiempo real
└── README.md               # Bitácora y documentación del proyecto
```

---

## 🚀 Cómo Ejecutar

### 1. Activar el entorno virtual (PowerShell)
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Ejecutar prueba rápida de diagnóstico
Toma una instantánea, analiza brillo, contraste y guarda el archivo en `captures/`:
```powershell
python test_camera.py
```

### 3. Abrir ventana de video en vivo
Abre el flujo en tiempo real (presiona la tecla `q` en la ventana para cerrar):
```powershell
python view_stream.py
```

---

## 🎯 Próximo Paso: Fase 2 (Identificación con IA)

Con la cámara funcionando, el siguiente objetivo es integrar el modelo de Inteligencia Artificial para identificar lo que necesites:

1. **Detección de Objetos en Tiempo Real:** Detección de personas, celulares, botellas, sillas u 80 clases comunes mediante **YOLOv8** / **YOLO11**.
2. **Reconocimiento Facial o Poses:** Detección de rostros, landmarks faciales o postura corporal usando **MediaPipe** o modelos DNN de OpenCV.
3. **Clasificación / Detección Específica:** Entrenamiento o fine-tuning para objetos específicos de tu entorno o proceso particular.
4. **Lectura de Códigos / Texto:** Lectura de códigos QR/barras o reconocimiento óptico de caracteres (OCR).

*Pendiente de definir por el usuario qué elementos o eventos específicos se desea que la cámara identifique.*
