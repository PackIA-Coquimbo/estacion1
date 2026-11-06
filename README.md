# PackIACamara — Estación 1

La estación 1 fotografía las naranjas mientras pasan ante la cámara. Detecta una fruta dentro de la zona central marcada en el visor, espera una imagen con buen encuadre, iluminación, contraste y enfoque, y guarda un recorte de la naranja para la estación 2. **No clasifica el estado de la fruta.**

## Uso

En Windows, abre [`LogicaPackIA/iniciar_detector_naranja.bat`](LogicaPackIA/iniciar_detector_naranja.bat). También puedes ejecutar `python -m src.main` desde la raíz del proyecto. Pulsa `Q` o `Esc` para cerrar el visor.

El programa puede detectar varias naranjas separadas dentro de la zona marcada y guarda un recorte por cada una. Hace seguimiento de cada fruta visible para evitar nuevas fotos mientras permanece en el cuadro. Si dos naranjas se tocan y forman una sola silueta, la separación aún requiere pruebas con la cinta real.

Los recortes de la naranja se guardan en `LogicaPackIA/captures/estacion1/`. Cada recorte también se copia a `LogicaPackIA/outbox_e2/` junto a un JSON con fecha, identificador, coordenadas de la naranja y tamaño del recorte. La entrega figura como `pending` porque la estación 2 todavía no ha definido su receptor. No se marca como enviada hasta completar esa integración.

`LogicaPackIA/detect_orange.py` conserva compatibilidad con el nombre anterior, pero también inicia solo la captura de estación 1.

## Ejecución sin internet y traslado a Raspberry Pi

La captura y la bandeja de salida funcionan completamente en el equipo local: el programa no descarga modelos ni consulta servicios externos. Prepara las dependencias antes de la demostración. Las fotos quedan en disco aunque la estación 2 no esté conectada.

En Raspberry Pi OS, instala previamente `python3-opencv` y `python3-numpy` desde los repositorios del sistema. Si se usa una cámara CSI de Raspberry Pi, instala también `python3-picamera2`. En el equipo de demostración se puede iniciar así, desde la raíz del proyecto:

```bash
# Cámara USB / V4L2
python3 -m src.main --backend opencv --headless --data-dir ~/packia-data

# Cámara CSI / Picamera2
python3 -m src.main --backend picamera2 --headless --data-dir ~/packia-data
```

Con `--headless` no se abre ninguna ventana; `Ctrl+C` detiene el programa. `--camera`, `--width` y `--height` permiten ajustar el dispositivo y la resolución. Con `--data-dir`, las fotos quedan en `captures/` y los pares JPG + JSON para estación 2 en `outbox_e2/` dentro del directorio indicado. Sin `--data-dir` se usan las carpetas del repositorio.

Para las dos cámaras USB previstas, se puede ejecutar el mismo programa por separado con `--backend opencv --camera 0 --camera-id cam_izquierda` y `--backend opencv --camera 1 --camera-id cam_derecha`, usando el mismo `--data-dir`. En Linux conviene usar los enlaces estables de `/dev/v4l/by-id/` o `/dev/v4l/by-path/` en `--camera`, porque los números `/dev/videoX` pueden cambiar tras reiniciar. Cada captura incluye `camera_id` y un identificador de seguimiento local. **Esta modalidad aún no empareja las dos vistas de una misma naranja**; hace falta un coordinador y calibración de ambas vistas para asignar un `fruit_id` común, especialmente cuando pasan varias frutas simultáneas.

Esta adaptación deja listo el código para probar en Raspberry Pi, pero aún debe verificarse con el modelo de Pi, la cámara, el montaje y la velocidad real de la cinta que se usarán en la demostración.
