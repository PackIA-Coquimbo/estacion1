# PackIACamara — Estación 1

La estación 1 detecta naranjas en la zona central de la cámara, comprueba encuadre, iluminación, contraste y enfoque, y guarda un recorte por fruta. Puede seguir varias naranjas separadas en una misma imagen. **No clasifica su estado**: eso corresponde a la estación 2.

--MEJORAS QUE FALTAN
1.- El programa captura ambas naranjas en la zona de captura pero si se ponen juntas no captura bien, hay que mejorar eso o que capture ambas dentro de la zona y se les envie a la estación 2 una foto con ambas naranjas.
2.- Acordar que necesita la estación 2: Se les enviarán una foto de cada cámara pero hay que ajustar formatos para que la enviemos y la reciban bien.
3.- Cuando la estación 6 tenga la cinta en funcionamiento hay que ir probando la cámara con la cinta moviéndose.
4.- Cualquier mejora que añadan considerar que más adelante debe funcionan en sistema embebido como raspberry pi
5.- Cambiar resolución a 480x640 porque esa es la que están ocupando para trabajar en la estación 2.

## Uso en PC

En Windows, abre [`logica/iniciar_detector_naranja.bat`](logica/iniciar_detector_naranja.bat), o ejecuta `python -m src.main` desde la raíz del repositorio. La ventana muestra la zona de captura; pulsa `Q` o `Esc` para salir. También se puede ejecutar sin ventana con `python -m src.main --headless` y detener con `Ctrl+C`.

Los recortes se guardan en `logica/captures/estacion1/`. Cada JPG se copia a `logica/outbox_e2/` junto a un JSON con identificador, cámara, hora, coordenadas y nitidez. La entrega a estación 2 permanece en `pending` porque el receptor todavía no está definido. Consulta el [borrador de integración](docs/propuesta_integracion_estacion2.md).

## Dos cámaras USB

El mismo programa puede ejecutarse una vez por cámara, con un identificador diferente y una carpeta de datos compartida. Por ejemplo:

```bash
python -m src.main --backend opencv --camera 0 --camera-id cam_izquierda --data-dir datos
python -m src.main --backend opencv --camera 1 --camera-id cam_derecha --data-dir datos
```

Las fotos incluyen `camera_id` y un seguimiento local. **Aún falta el coordinador que relacione las dos fotos de una naranja mediante un `fruit_id` común.** Como ambas cámaras mirarán la misma zona desde ángulos distintos, ese emparejamiento requiere calibración con el montaje real. Si dos frutas se tocan y forman una sola silueta, su separación tampoco está validada todavía.

## Ejecución offline en Raspberry Pi

La captura no descarga modelos ni necesita internet. Prepara las dependencias antes de la demostración. Con dos cámaras USB, instala previamente `python3-opencv` y `python3-numpy` en Raspberry Pi OS y prueba ambas cámaras a la vez en el equipo definitivo.

```bash
python3 -m src.main --backend opencv --camera 0 --camera-id cam_izquierda --headless --data-dir ~/packia-data
```

En Linux, `--camera` también admite rutas de `/dev/v4l/by-id/` o `/dev/v4l/by-path/` para evitar que cambie la asignación de cámara tras reiniciar. `--width` y `--height` ajustan la resolución. Con `--data-dir`, fotos y bandeja de salida se almacenan fuera del código para facilitar el traslado a la Raspberry Pi.

La prueba en el PC confirma el flujo de una cámara; faltan pruebas con dos cámaras y con la cinta en movimiento.
