# PackIA — Estación 1: captura de naranjas

Estación de adquisición de imágenes para el proyecto PackIA. Localiza una naranja con
YOLO, reúne varias vistas de dos cámaras USB y prepara las fotos utilizables para
[la estación 2](https://github.com/PackIA-Coquimbo/estacion2), encargada de clasificar
su estado. Una foto aceptada puede mostrar una naranja sana, verde o deteriorada:
la aceptación de E1 corresponde a la calidad de la imagen.

## Estado actual

- Detección con el modelo local `models/yolov8n.pt`, confianza predeterminada 0.55.
- Reintentos ampliados de la zona central cuando falla la búsqueda inicial.
- Control de nitidez, brillo, contraste y saturación dentro de la fruta detectada.
- Ráfagas acotadas para completar el ciclo en **≤ 2 segundos**: hasta 10 candidatas por
  cámara en un máximo de 1.6 s (`--burst-interval-ms 100`, `--burst-min-change 0`),
  conservando la **mejor vista por cámara** (`--burst-keep 1`, 2 fotos en total con dos cámaras)
  y enviando las descartadas a `evidencia_estacion1/rechazadas/` para auditoría.
- JPG de 480×640 píxeles (ancho×alto), recortados alrededor de la naranja, con margen
  y bordes para conservar su proporción.
- Identificadores comunes de lote, fruta, captura y ráfaga. Los eventos pueden contener
  una o dos vistas; el manifiesto señala cuándo falta alguna cámara.
- Recopilación de ejemplos, etiquetado manual y exportación de datasets separados por
  naranja física, además de comandos de entrenamiento y evaluación.
- Emisor secuencial compatible con el protocolo JPEG → trigger → resultado → ACK del
  listener actual de E2, para procesos que comparten una carpeta en el mismo equipo.

Se trabaja con **una naranja física a la vez**. Para fotografiar distintos lados hay
que girarla físicamente; la ráfaga no garantiza por sí sola una cobertura de 360°.

## Instalación y cámaras en Windows

Probado localmente con Python 3.11 y dos cámaras USB. Desde la raíz del proyecto:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\iniciar_estacion1_dos_camaras.bat
```

El lanzador usa `.venv` si existe. Enumera las cámaras por su nombre y, si hay más de
dos, permite seleccionar las externas. Cierra las aplicaciones que estén utilizando
las cámaras. Para comprobar índices y resolución:

```powershell
.\.venv\Scripts\python.exe -m src.probe_cameras 0 1
```

Si `py` no está disponible, crea el entorno con la ruta del Python instalado.
El modelo debe existir en disco; la captura no lo descarga automáticamente.
La instalación de dependencias sí requiere acceso a sus paquetes.

## Capturar varias vistas

Coloca ambas cámaras hacia la misma zona y mantén fondo, iluminación y montaje fijos.
Desde el lanzador puedes elegir modo manual o automático. También puedes ejecutar:

```powershell
.\.venv\Scripts\python.exe -m src.paired_capture --lot Prueba_001 --camera 0 --camera-2 1
```

| Tecla | Acción |
|---|---|
| R | Iniciar o terminar una ráfaga manual de la naranja actual |
| C | Capturar un evento individual; en dos cámaras exige que ambas vistas sean válidas |
| T | Guardar originales para revisar y entrenar, incluso si la detección falla |
| N | Cambiar el ID para una nueva naranja física, cuando no hay una ráfaga activa |
| B | Calibrar fondo vacío, necesario únicamente para el detector alternativo por fondo |
| Q / Esc | Salir y guardar las vistas pendientes de la ráfaga |

En modo automático (`--auto`, opción por defecto `[S]` en el lanzador) la ráfaga se
cierra automáticamente tras `--burst-duration 1.6` s (o al alcanzar `--burst-count 10`
candidatas por cámara) y espera a que la fruta salga de la zona antes de rearmarse para
la siguiente naranja. Con YOLO basta al menos un evento válido para publicar; las vistas
descartadas de la ráfaga (fuera del Top seleccionado o con nitidez < 70% de la mejor toma de esa
cámara) se guardan aparte en `evidencia_estacion1/rechazadas/`.

Para ajustar la duración, cantidad de candidatas y cuántas conservar:

```powershell
.\.venv\Scripts\python.exe -m src.paired_capture --lot Prueba_001 --camera 0 --camera-2 1 --auto --burst-count 10 --burst-keep 1 --burst-duration 1.6 --burst-interval-ms 100
```

`--burst-count` admite de 1 a 32 candidatas por cámara (`10` por defecto). `--burst-keep`
define cuántas mejores vistas conservar por cámara (`1` por defecto = 1 mejor por ángulo; `0` conserva todas).
`--burst-min-change 0` permite capturar sobre naranja quieta; puedes subirlo (ej. `1.5`)
si la fruta gira para omitir imágenes parecidas. La ventana muestra confianza YOLO, nitidez,
brillo y el motivo de rechazo. Existen ajustes separados para cámara 1 mediante
`--yolo-confidence-2`, `--min-sharpness-2` y `--min-contrast-2`; deben validarse con fotos.

## Archivos generados e integración con E2

| Carpeta | Contenido |
|---|---|
| `salidas_estacion2/<lote>/` | JPEG aceptados (mejor foto por cámara = 2 fotos con 2 cámaras) y manifiestos JSON |
| `evidencia_estacion1/rechazadas/` | Capturas individuales rechazadas y descartes de ráfaga, a resolución original |
| `dataset_naranjas/raw/` | Ejemplos originales y anotaciones para revisión |
| `runs/` | Resultados locales de entrenamiento y evaluación |

Las tomas descartadas durante una ráfaga por ranking o nitidez relativa se archivan en
`evidencia_estacion1/rechazadas/<lote>/` fuera de `salidas_estacion2/`; pulsa T si además
deseas guardar muestras para entrenamiento. Los manifiestos incluyen `id_fruta`, `id_rafaga`,
`indice_rafaga`, `total_rafaga`, cámaras esperadas, vistas incompletas, métricas y hashes.
`total_rafaga` cuenta eventos: cada evento puede contener una o dos fotos.

El listener actual de E2 recibe una imagen por turno y no consume nuestros manifiestos
ni combina las distintas vistas de una fruta. El emisor espera ACK antes de avanzar,
conserva pendientes en caso de timeout y registra localmente cada respuesta ligada a
la fruta y la cámara. Debe existir un único productor del canal.

Con el listener E2 ya iniciado y su `--shm-dir` apuntando a la misma carpeta:

```powershell
.\.venv\Scripts\python.exe -m src.send_e2 --outbox salidas_estacion2 --channel C:\PackIA\canal
```

Solo se envían capturas aceptadas con método YOLO; las capturas antiguas por fondo se
omiten. E1 no inicia envíos externos automáticamente. En equipos distintos falta un
protocolo de red acordado. En Linux `/dev/shm` es memoria RAM; una carpeta temporal en
Windows no garantiza ese comportamiento. Véase [el contrato y sus límites](docs/integracion_yolo_e2.md).

## Recopilar datos y entrenar

Abre `recolectar_ejemplos.bat`. En este modo T guarda ambas vistas con el mismo ID,
N cambia a otra naranja física y las capturas automáticas no adelantan el identificador.
Guarda varios giros de cada fruta e incluye ejemplos que YOLO rechace.

```powershell
.\.venv\Scripts\python.exe -m src.train_detector label
.\.venv\Scripts\python.exe -m src.train_detector export --destination dataset_naranjas/v1
.\.venv\Scripts\python.exe -m src.train_detector train --data dataset_naranjas/v1/data.yaml --model models/yolov8n.pt --epochs 60
```

Las etiquetas requieren revisión humana. La exportación mantiene juntas todas las
vistas de una naranja física y conserva la asignación train/val/test para versiones
posteriores. El operador debe registrar correctamente la identidad de cada fruta,
incluido cuando se reutiliza en otra sesión. El dataset local y sus anotaciones se
mantienen fuera del control de versiones.

Los pesos entrenados no se adoptan automáticamente. Evalúa `weights/best.pt` de la
carpeta que imprima Ultralytics y prueba con frutas nuevas antes de utilizarlo:

```powershell
.\.venv\Scripts\python.exe -m src.train_detector evaluate --data dataset_naranjas/v1/data.yaml --model runs/naranjas/detector/weights/best.pt
.\.venv\Scripts\python.exe -m src.paired_capture --lot Modelo_propio --camera 0 --camera-2 1 --yolo-model runs/naranjas/detector/weights/best.pt
```

Consulta [la guía de etiquetado, entrenamiento y evaluación](docs/entrenar_detector.md).
Los pesos operativos siguen siendo genéricos: todavía no se ha validado un modelo propio.

## Pruebas y límites conocidos

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

La versión actual cuenta con 32 pruebas unitarias que cubren ráfagas acotadas, selección
por ranking de calidad (Top 1 / Top N), calidad de imagen, recortes, agrupación del dataset, lanzador de cámaras
y el protocolo del listener E2 con clasificador simulado. El fixture de
`tests/fixtures/e2_station_listener_reference.py` reproduce el contrato JPEG/trigger/ACK
de E2 para validar el emisor sin acoplar el modelo clasificador.

En ocho fotos conocidas de cuatro frutas, la búsqueda ampliada pasó de cinco a siete
detecciones al mismo umbral 0.55. Las siete pasaron los filtros de imagen. Estos ejemplos
se usaron para desarrollar la mejora y no constituyen una evaluación independiente.
Queda una vista con confianza baja (revisión de piloto externa al repositorio).

El modelo genérico puede confundir naranjas con manzanas o fallar con formas y superficies
distintas. YOLO de detección no garantiza detectar una mano que tape la fruta.
También faltan pruebas con cinta en movimiento, Raspberry Pi y el clasificador real
de E2. La [validación anterior de dos cámaras](docs/validacion_dos_camaras_2026-11-13.md)
corresponde al modo de captura previo.

## Linux y modo alternativo

El lanzador `iniciar_estacion1_dos_camaras.sh` identifica dispositivos USB mediante udev
y rutas persistentes de `/dev/v4l/by-id` o `/dev/v4l/by-path`. Requiere `udevadm`, Python,
un entorno virtual y las dependencias del proyecto. La configuración de YOLO debe
validarse en el equipo Linux definitivo, especialmente en Raspberry Pi.

El detector anterior por fondo se mantiene disponible:

```bash
python -m src.paired_capture --lot Prueba_001 --camera 0 --camera-2 1 --detector background --output-framing crop
```

En ese modo se calibra la zona vacía con B. `python -m src.main` conserva el flujo
anterior de seguimiento de varias frutas, con fotos en `logica/captures/estacion1/`
y bandeja en `logica/outbox_e2/`; usa su propia interfaz y no es el flujo YOLO descrito arriba.

## Mejoras futuras

1. **Dataset y modelo propios.** Reunir más frutas, variedades, estados y ángulos de ambas
   cámaras; añadir negativos y casos difíciles. Medir precisión, recall y errores por
   cámara con naranjas físicas nuevas antes de sustituir los pesos.
2. **Oclusiones y enfoque.** Detectar manos y fruta parcialmente tapada; evaluar segmentación
   y calibrar el filtro de nitidez con ejemplos revisados del montaje real.
3. **Cobertura de vistas.** Medir diversidad de ángulos, seleccionar las mejores fotos por
   fruta y señalar cuándo falta una vista; probar un mecanismo de rotación controlada.
4. **Contrato completo con E2.** Acordar IDs de fruta/vista en solicitudes y respuestas,
   combinar resultados por naranja y validar su CNN con los recortes producidos por E1.
   Incorporar transporte de red si las estaciones usan equipos separados.
5. **Cinta y varias frutas.** Probar con estación 6 a diferentes velocidades, medir pérdidas
   y duplicados y después resolver asociación entre cámaras y frutas que se tocan.
6. **Raspberry Pi.** Medir FPS, latencia, RAM y temperatura con ambas cámaras; comparar
   exportación ONNX y cuantización sin perder detalle útil para E2.
7. **Operación y trazabilidad.** Simplificar el etiquetado, registrar versiones de modelo y
   dataset, añadir recuperación de envíos tras interrupciones y comparar modelos antes
   de adoptarlos. Revisar límites de almacenamiento y retención de evidencias locales.

La prioridad inmediata es ampliar el dataset y validar el detector con frutas distintas;
la captura de más imágenes por sí sola no entrena el modelo.
