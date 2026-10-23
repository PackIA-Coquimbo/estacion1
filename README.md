# Estación 1 - Recepción, Detección y Captura (PackIA)

Módulo de visión artificial desarrollado en Python para la **Estación 1** del proyecto [PackIA-Coquimbo](https://github.com/PackIA-Coquimbo). El servicio se encarga de la recepción en línea de cajas de papayas o unidades individuales en la cinta de entrada, realizando la detección en tiempo real, evaluación de calidad de captura (iluminación, enfoque y encuadre) y envío de la imagen óptima validada hacia la **Estación 2** (análisis visual de calidad).

---

## Estado actual del proyecto

La etapa actual está orientada a la definición de arquitectura, documentación y orden estructural del proyecto:
- **Pipeline de captura de video**: Definición del flujo de lectura de cámara en tiempo real (webcam, stream RTSP o video de prueba) con OpenCV.
- **Detección y validación de ROI**: Delimitación del área de interés (*Region of Interest* - ROI) para confirmar que la caja o papaya esté correctamente encuadrada antes de la captura.
- **Control de calidad fotográfica**: Establecimiento de umbrales métricos (brillo medio, contraste y nitidez/enfoque mediante varianza del Laplaciano).
- **Despacho hacia Estación 2**: Definición del mecanismo de transferencia del fotograma o recorte validado con sus metadatos de lote y caja.
- **Estructura modular limpia**: Organización de módulos desacoplados para cámara, detección, calidad y cliente de despacho.

---

## Alcance implementado

### Flujo de operación de la Estación 1

| Etapa | Proceso | Descripción |
| :--- | :--- | :--- |
| **1. Captura** | Ingesta de video / cámara | Lectura continua del flujo de cámara en la línea de entrada. |
| **2. Detección** | Localización y ROI | Identificación de la papaya o caja y validación de que se encuentre en la posición correcta de captura. |
| **3. Validación** | Control de calidad de imagen | Evaluación de umbrales óptimos de brillo, contraste y enfoque para descartar imágenes subexpuestas, sobreexpuestas o borrosas. |
| **4. Despacho E2** | Envío a Estación 2 | Transmisión del fotograma/recorte óptimo a la **Estación 2** para que ejecute la clasificación de defectos y calidad visual. |

---

## Integración con Estación 2 (Análisis Visual)

La Estación 2 depende directamente de la calidad del material generado por la Estación 1. Una vez validada la captura (`validez_imagen = true` y `posicion_correcta = true`), la Estación 1 empaqueta y transfiere:
- **Fotograma o recorte óptimo**: Imagen en alta definición debidamente encuadrada y enfocada.
- **Metadatos de trazabilidad**:
  - `id_lote`: Identificador del lote en procesamiento.
  - `id_caja`: Identificador secuencial de la caja o unidad.
  - `timestamp`: Marca temporal exacta de la captura (formato ISO 8601).

De esta manera, la Estación 2 puede concentrarse de manera exclusiva en sus modelos de clasificación fitosanitaria y defectos superficiales, sin perder recursos reprocesando imágenes borrosas, mal iluminadas o fuera de posición.

---

## Estructura del proyecto

```text
estacion1/
├── src/
│   ├── __init__.py
│   ├── main.py              # Orquestador del flujo y bucle principal
│   ├── camera.py            # Gestión de captura de cámara / streams de video
│   ├── detector.py          # Detección de papayas/cajas y validación de posición (ROI)
│   ├── image_quality.py     # Análisis de calidad fotométrica (brillo, contraste, nitidez)
│   ├── client_e2.py         # Despacho de imágenes validadas hacia la Estación 2
│   └── config.py            # Configuración, parámetros y umbrales de captura
├── tests/                   # Datos de prueba, imágenes y validación offline
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
├── .dockerignore
└── README.md
```

### Archivos principales

- **`src/main.py`**: Punto de entrada y orquestador del ciclo continuo de captura y procesamiento.
- **`src/camera.py`**: Control de hardware de cámara (USB/RTSP/video local).
- **`src/detector.py`**: Algoritmos de visión para localizar el objeto y verificar si está dentro de la ROI.
- **`src/image_quality.py`**: Cálculo de métricas fotométricas (brillo medio, contraste RMS y nitidez).
- **`src/client_e2.py`**: Módulo cliente para transferir imágenes y metadatos hacia la Estación 2.
- **`src/config.py`**: Parámetros de umbrales y variables de configuración.

---

## Ejecución local (Referencia futura)

### Entorno virtual de Python

1. Crear y activar el entorno virtual:
```bash
python -m venv venv
# En Windows (PowerShell):
venv\Scripts\Activate.ps1
# En Linux/macOS:
source venv/bin/activate
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

3. Ejecutar el servicio:
```bash
python -m src.main
```

---

## Observaciones de diseño

- **Filtro temprano de calidad**: La Estación 1 actúa como el primer filtro del proceso. Al descartar de inmediato capturas defectuosas, evita sobrecargar los modelos analíticos de la Estación 2.
- **Separación de responsabilidades**: La Estación 1 no realiza análisis de madurez ni detección de defectos fitosanitarios; su responsabilidad concluye al entregar una captura óptima y validada a la Estación 2.

---

## Tecnologías consideradas

- **Python 3.11**
- **OpenCV (`opencv-python`)**: Captura de fotogramas, preprocesamiento y filtros de visión artificial.
- **NumPy**: Operaciones matriciales y cálculo de estadísticas de imagen.
- **HTTPX / Requests**: Comunicación HTTP con la Estación 2.
- **Docker / Docker Compose**: Contenerización y estandarización de despliegue.
