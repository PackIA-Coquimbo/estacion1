# Estación 1: captura de naranjas

Esta estación detecta una naranja en la zona central marcada del visor, comprueba encuadre, luz, contraste y nitidez, y guarda **un recorte centrado en la fruta**. No decide si la fruta está buena o dañada: esa clasificación corresponde a la estación 2.

## Iniciar

Ejecuta `iniciar_detector_naranja.bat` desde Windows o `python -m src.main` desde la raíz del repositorio. La ventana se abre en tamaño 1440 × 810. Pulsa `Q` o `Esc` para salir.

La foto se toma automáticamente cuando aparece una naranja bien encuadrada y nítida. El sistema puede registrar varias naranjas separadas en la zona marcada, cada una con su seguimiento local. La asociación de vistas entre dos cámaras aún está pendiente de calibración.

## Fotos y entrega

- Recortes de fruta: `captures/estacion1/naranja_<id>.jpg`.
- Bandeja para estación 2: `outbox_e2/`, con una copia `.jpg` y un `.json` por captura. El JSON contiene identificador, hora, tamaño, encuadre y métrica de nitidez; `delivery_status` queda en `pending`.

La estación 2 aún no ha definido receptor ni formato de transmisión. Por eso el programa **no afirma que haya enviado** la foto. Cuando se acuerde el contrato de integración, se conectará esta bandeja al receptor de estación 2.

`detect_orange.py` es una entrada de compatibilidad que inicia el mismo flujo de captura. El lanzador `.bat` usa `src.main`.

Para ejecutar en Raspberry Pi sin monitor y sin internet, consulta la sección de Raspberry Pi en el `README.md` de la raíz del proyecto. El programa no necesita red para detectar ni guardar fotos.
