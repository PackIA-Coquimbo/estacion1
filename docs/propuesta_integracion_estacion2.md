# Propuesta para acordar la entrega entre estaciones 1 y 2

**Estado:** borrador para conversar con el equipo de estación 2. Nada de esta interfaz está aprobado ni implementado como envío automático.

## Decisiones que deben tomar juntos

1. **Ubicación y conexión.** ¿Ambas estaciones correrán en el mismo equipo, o en equipos distintos unidos por una red local? Si comparten equipo, una carpeta local con confirmación de consumo es simple. Si son equipos distintos, recomendamos una API HTTP en la red local. Ninguna opción requiere internet.
2. **Vistas por fruta.** Se planifican dos cámaras mirando la misma zona desde ángulos distintos. Estación 2 debe confirmar si esas dos vistas bastan para evaluar la superficie y cómo tratar una vista faltante. Ambas fotos deben llevar un mismo `fruit_id`, además del `capture_id` único por foto y el `camera_id`.
3. **Calidad mínima.** Definir tamaño mínimo de la naranja en píxeles, formato, compresión JPEG, tolerancia a desenfoque, iluminación, fondo y tiempo máximo desde que entra la fruta hasta que se recibe la imagen. Las fotos actuales suelen tener recortes de unos cientos de píxeles; hay que probar si permiten ver los defectos que estación 2 busca.
4. **Identidad.** Acordar identificador de estación, lote y fruta, y qué ocurre si la misma fruta vuelve a pasar. `capture_id` debe ser único y estable en los reintentos.
5. **Confirmación y errores.** Estación 2 debe confirmar que guardó el archivo y asociarlo al mismo `capture_id`. Definir tiempo de espera, reintentos, duplicados, caída de red y cuándo se puede borrar una copia local.
6. **Salida de estación 2.** Confirmar si estación 1 necesita recibir un resultado para sincronizarse con la cinta o si solo entrega imágenes. La clasificación sigue siendo responsabilidad de estación 2.

## Contrato HTTP propuesto si son equipos distintos

- `POST /api/v1/capturas` en la red local, `multipart/form-data` con una parte `image` (`image/jpeg`) y una parte `metadata` (`application/json`). El nombre de la parte y la ruta son **propuestas**, sujetas al acuerdo.
- La foto es un recorte de la naranja sin interfaz dibujada. No incluir imagen codificada en base64 dentro del JSON.
- Metadatos mínimos propuestos:

```json
{
  "schema_version": 1,
  "capture_id": "E1-20261106-154344-133955",
  "station_id": "E1",
  "camera_id": "cam_izquierda",
  "fruit_id": "E1-fruta-000123",
  "view_index": 1,
  "view_count": 2,
  "captured_at": "2026-11-06T18:43:44.172Z",
  "image_width": 480,
  "image_height": 640,
  "sha256": "<hash del JPEG>"
}
```

`fruit_id`, `view_index` y `view_count` siguen siendo campos **propuestos para la integración automática de dos cámaras**. El modo local `src.paired_capture` usa `id_fruta` para asociar dos vistas cuando pasa una fruta a la vez; todavía no implementa este contrato HTTP. `lot_id` se agrega si el proceso físico lo proporciona. Los JPG aceptados se guardan a 480×640 píxeles (ancho×alto). La resolución fija no sustituye la comprobación de detalle real sobre la fruta. El tamaño de la imagen y el hash permiten verificar que se recibió el archivo correcto. Las coordenadas del recorte pueden enviarse como campos adicionales si estación 2 las necesita.

## Dos cámaras y varias naranjas simultáneas

El mismo módulo de detección y calidad puede correr para cada cámara. Cada una produce fotos con su propio `camera_id` y número de seguimiento local. La estación 1 necesita además **un coordinador común** que asigne un `fruit_id` a la naranja física y relacione las dos vistas; dos procesos independientes no pueden inferir con seguridad esa relación solo por la hora si hay varias naranjas juntas.

Como ambas cámaras mirarán la misma zona, la asociación debería basarse en una calibración geométrica de sus vistas y un disparo o reloj compartido. Definir con el montaje real cuál cámara genera la identidad principal, cómo se corresponden las posiciones entre imágenes y qué tolerancia temporal se acepta. Si una cámara no logra una buena foto, registrar explícitamente la vista faltante y acordar si estación 2 procesa la vista disponible o solicita repetir la captura.

**Hardware definido hasta ahora:** dos cámaras USB; modelo de Raspberry Pi pendiente. Para elegirlo hay que comprobar que ambas cámaras funcionen a la resolución requerida, con alimentación y ancho de banda suficientes, mientras el procesamiento mantiene el ritmo de la cinta. En Raspberry Pi OS conviene fijar cada cámara por `/dev/v4l/by-id/` o `/dev/v4l/by-path/` y no asumir que `/dev/video0` y `/dev/video1` conservarán el orden tras un reinicio. Véanse la [documentación V4L2 del kernel](https://cdn.kernel.org/doc/html/latest/userspace-api/media/v4l/open.html) y las [especificaciones de energía USB de Raspberry Pi](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html).

El detector actual puede seguir varias naranjas **separadas** en una cámara y guardar una foto por cada una. Si las frutas se tocan o se ocultan entre sí, la segmentación por color puede unirlas; esa situación requiere pruebas con la cinta y posiblemente separación por instancias antes de afirmar que cada fruta tendrá dos fotos.

- Respuesta recomendada: `201 Created` cuando estación 2 **persistió** la captura, con `capture_id` y un identificador propio. Si devuelve `202 Accepted`, debe existir una forma posterior de consultar si se procesó. Los errores de validación deben distinguirse de errores temporales.
- Estación 2 debe tratar un `capture_id` repetido como el mismo envío y responder sin crear otra fruta. Así estación 1 puede reintentar después de un corte sin duplicar registros.
- Estación 1 mantiene JPG y JSON en su bandeja local hasta recibir confirmación. Después marca el envío como entregado; no borra la única copia inmediatamente.

## Mejoras pendientes en estación 1

1. Implementar el transporte y la confirmación una vez acordado el contrato; hoy solo existe la bandeja `outbox_e2` con estado `pending`.
2. Medir con la cinta en movimiento: capturas perdidas, duplicadas, desenfoque, tiempo por fruta y espacio ocupado en disco.
3. Ajustar cámara, distancia, iluminación y fondo para que la naranja ocupe suficientes píxeles. Fijar los umbrales de calidad usando ejemplos reales del montaje.
4. Añadir recuperación de cámara y vigilancia del espacio libre para el funcionamiento continuo de la Raspberry Pi.
5. Probar en la Raspberry Pi y cámara definitivas, sin conexión a internet, antes de la demostración.

## Referencias del formato propuesto

- [RFC 7578: `multipart/form-data`](https://www.rfc-editor.org/rfc/rfc7578)
- [RFC 9110: respuestas HTTP e idempotencia](https://www.rfc-editor.org/rfc/rfc9110)
- [RFC 3339: fechas y horas con zona](https://www.rfc-editor.org/rfc/rfc3339)
