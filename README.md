# PackIACamara — Estación 1

La estación 1 detecta naranjas en la zona central de la cámara, comprueba encuadre, iluminación, contraste y enfoque, y guarda un recorte por fruta. Puede seguir varias naranjas separadas en una misma imagen. **No clasifica su estado**: eso corresponde a la estación 2.

--MEJORAS QUE FALTAN
1.- El programa captura ambas naranjas en la zona de captura pero si se ponen juntas no captura bien, hay que mejorar eso o que capture ambas dentro de la zona y se les envie a la estación 2 una foto con ambas naranjas.
2.- Acordar que necesita la estación 2: Se les enviarán una foto de cada cámara pero hay que ajustar formatos para que la enviemos y la reciban bien.
3.- Cuando la estación 6 tenga la cinta en funcionamiento hay que ir probando la cámara con la cinta moviéndose.
4.- Cualquier mejora que añadan considerar que más adelante debe funcionan en sistema embebido como raspberry pi

La resolución de los JPG aceptados ya se ajustó a **480×640 píxeles (ancho×alto)**. Falta comprobar con imágenes reales que la fruta conserve suficiente detalle para la estación 2.

## Uso en PC

En Windows, abre [`logica/iniciar_detector_naranja.bat`](logica/iniciar_detector_naranja.bat), o ejecuta `python -m src.main` desde la raíz del repositorio. La ventana muestra la zona de captura; pulsa `Q` o `Esc` para salir. También se puede ejecutar sin ventana con `python -m src.main --headless` y detener con `Ctrl+C`.

Los recortes se guardan en `logica/captures/estacion1/`. Cada JPG se copia a `logica/outbox_e2/` junto a un JSON con identificador, cámara, hora, coordenadas y nitidez. La imagen guardada mide 480×640 sin deformar la fruta; si el recorte original tiene otra proporción, se añaden bordes. El JSON informa `image_width`, `image_height`, el tamaño del recorte original y `output_framing`. La entrega a estación 2 permanece en `pending` porque el receptor todavía no está definido. Consulta el [borrador de integración](docs/propuesta_integracion_estacion2.md).

## Dos cámaras USB

El mismo programa puede ejecutarse una vez por cámara, con un identificador diferente y una carpeta de datos compartida. Por ejemplo:

```bash
python -m src.main --backend opencv --camera 0 --camera-id cam_izquierda --data-dir datos
python -m src.main --backend opencv --camera 1 --camera-id cam_derecha --data-dir datos
```

Las fotos incluyen `camera_id` y un seguimiento local. **Aún falta el coordinador que relacione las dos fotos de una naranja mediante un `fruit_id` común.** Como ambas cámaras mirarán la misma zona desde ángulos distintos, ese emparejamiento requiere calibración con el montaje real. Si dos frutas se tocan y forman una sola silueta, su separación tampoco está validada todavía.

### Pruebas de dos vistas en un solo PC

Para probar **una fruta a la vez** con las dos cámaras, usa el modo de captura pareada. Este modo abre ambas cámaras en un mismo proceso y asigna un `id_fruta` común a sus dos JPG. No resuelve la asociación de varias frutas simultáneas entre cámaras.

```powershell
python -m src.probe_cameras 0 1
python -m src.paired_capture --lot Prueba_001 --camera 0 --camera-2 1
```

También puedes abrir `iniciar_estacion1_dos_camaras.bat`. El comprobador abre ambas cámaras a la vez e informa la resolución real de cada una. Si los índices 0 y 1 no funcionan, prueba otros, por ejemplo `1 2`, y cierra aplicaciones que estén usando las cámaras. En Windows se prueban DirectShow, Media Foundation y el backend predeterminado. El modo pareado solicita 1280×720 como resolución de captura; puedes cambiarla con `--capture-width` y `--capture-height`. El tamaño de salida sigue siendo 480×640.

Coloca las dos cámaras de forma que vean la misma zona. Con la zona vacía, pulsa **B** para calibrar el fondo de ambas. Presenta una naranja, pulsa **C** y revisa que `salidas_estacion2/Prueba_001/` contenga dos JPG de 480×640 y un JSON con el mismo `id_fruta`. Las capturas rechazadas se conservan a resolución original en `evidencia_estacion1/rechazadas/` para revisar luz, enfoque y posición. Si giras y vuelves a fotografiar una naranja, registra qué nuevos `id_fruta` corresponden a esa naranja física.

Después de obtener pares consistentes en manual, prueba `--auto` con una fruta por paso y espacio entre frutas. Vuelve a pulsar **B** antes de la prueba automática. Anota cuántas frutas pasaron, cuántos pares se aceptaron y cuáles se perdieron o duplicaron. Los controles de captura calibran la adquisición de imágenes; el entrenamiento de un clasificador de defectos corresponde a estación 2 y necesita etiquetas correctas por imagen.

## Ejecución offline en Raspberry Pi

La captura no descarga modelos ni necesita internet. Prepara las dependencias antes de la demostración. Con dos cámaras USB, instala previamente `python3-opencv` y `python3-numpy` en Raspberry Pi OS y prueba ambas cámaras a la vez en el equipo definitivo.

```bash
python3 -m src.main --backend opencv --camera 0 --camera-id cam_izquierda --headless --data-dir ~/packia-data
```

En Linux, `--camera` también admite rutas de `/dev/v4l/by-id/` o `/dev/v4l/by-path/` para evitar que cambie la asignación de cámara tras reiniciar. `--width` y `--height` ajustan la resolución. Con `--data-dir`, fotos y bandeja de salida se almacenan fuera del código para facilitar el traslado a la Raspberry Pi.

La prueba documentada en PC confirma el flujo de una cámara. El modo pareado y la salida 480×640 cuentan con pruebas automáticas, pero faltan pruebas físicas con las dos cámaras y con la cinta en movimiento.
