# Integración YOLO de Estación 1 con Estación 2

Este documento resume el contrato vigente implementado en [`src/client_e2.py`](../src/client_e2.py) y [`src/send_e2.py`](../src/send_e2.py).

## 1. Bandeja local (`salidas_estacion2/<lote>/`)

Cada evento aceptado genera:
- Una o dos imágenes JPG de `480×640 px` (calidad `95`, `subsampling=0`), nombradas `<id_captura>_<camara>.jpg`.
- Un manifiesto `<id_captura>.json` escrito atómicamente después de las imágenes, con:
  - `id_lote`, `id_fruta`, `id_captura`, `timestamp`
  - `id_rafaga`, `indice_rafaga`, `total_rafaga`
  - `estado_captura` (`"aceptada"`)
  - `camaras_esperadas`, `vistas_incompletas`, `motivos`
  - `vistas[]`: `camara`, `imagen`, `sha256`, `metodo_posicion`, `metricas_calidad`, `metricas_posicion`, `resolucion_origen_px`, `resolucion_guardada_px`, `encuadre_salida`

Las vistas descartadas de una ráfaga o capturas individuales rechazadas se guardan aparte en `evidencia_estacion1/rechazadas/<lote>/` y nunca se publican en `salidas_estacion2/`.

## 2. Emisor secuencial (`src.send_e2`)

Cuando Estación 1 y Estación 2 comparten carpeta local (`--channel` igual al `--shm-dir` del listener de E2):

```powershell
.\.venv\Scripts\python.exe -m src.send_e2 --outbox salidas_estacion2 --channel C:\PackIA\canal
```

1. Adquiere `estacion1_sender.lock` (con recuperación automática si el PID registrado ya no existe).
2. Filtra únicamente manifiestos con `estado_captura == "aceptada"` y todas sus vistas con `metodo_posicion == "yolo"`.
3. Verifica integridad `sha256` de cada JPG antes de enviarlo.
4. Escribe atómicamente `estacion_frame.jpg`, `estacion1_pending.json` y `estacion_trigger.flag`.
5. Espera `estacion_ack.flag` + `estacion2_result.json` y que E2 retire `estacion_trigger.flag`.
6. Guarda un comprobante en `salidas_estacion2/.e2_receipts/<id_captura>_<camara>.json` para evitar reenvíos duplicados.

## 3. Límites conocidos

- Requiere un único emisor activo por canal.
- Si E2 corre en un equipo distinto, sigue pendiente implementar el transporte de red descrito en [`docs/propuesta_integracion_estacion2.md`](propuesta_integracion_estacion2.md).
