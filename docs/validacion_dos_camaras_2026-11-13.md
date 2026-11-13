# Validación de dos cámaras y salida 480×640

**Fecha:** 13 de noviembre de 2026. **Equipo:** PC con Windows y dos cámaras USB.

## Resultado

- Las cámaras con índices `0` y `1` se abrieron simultáneamente y entregaron fotogramas de 1280×720 píxeles.
- Se presentaron cinco naranjas, una por vez: dos sanas, una con una mancha podrida visible desde un lado y dos podridas.
- Se seleccionó un par aceptado por cada naranja física. Los diez JPG resultantes miden 480×640 píxeles y cada par comparte `id_fruta` en su manifiesto original.
- Las cinco pruebas automáticas del repositorio pasaron, incluidas las de resolución y entrega pareada.

La prueba se hizo en modo manual. Las posiciones se confirmaron por el operador porque el fondo de la sala cambiaba continuamente. Se ajustaron las guías (`--roi` y `--roi-2`) al montaje de ese momento; esos valores no son una calibración general para otras cámaras o ubicaciones.

## Observaciones

1. Pulsar `C` varias veces con la misma fruta genera varias capturas aceptadas y hace avanzar `id_fruta` cada vez. En la primera prueba se registró cinco veces la misma naranja; se incluyó solo un par en el conjunto local de evaluación. El operador debe relacionar cada ID con la fruta física antes de usar las fotos como datos etiquetados.
2. La cámara 1 rechazó algunas capturas porque su guía incluía zonas oscuras detrás de la naranja. Ajustar la guía y la posición de la fruta permitió obtener un par aceptado. Un fondo controlado y las cámaras dirigidas hacia la zona de captura reducirían esa variación.
3. En la naranja con mancha unilateral, la lesión quedó visible en `camara_0` y no en `camara_1`. Las etiquetas de entrenamiento deben describir cada vista además del estado de la fruta física.
4. Los JPG de esta sesión incluyen parte de la sala, personas y pantallas. Se conservaron **localmente** para revisión; no se incorporaron al repositorio público.

Esta validación confirma el funcionamiento del programa y las dimensiones de salida en este PC. No valida la captura automática con cinta en movimiento, el funcionamiento en Raspberry Pi ni la capacidad de un clasificador para reconocer defectos. Cinco frutas y diez vistas forman una muestra piloto, no un conjunto suficiente para entrenar o medir un modelo.

## Próxima sesión de captura

1. Montar ambas cámaras de forma fija hacia un fondo uniforme y comprobar que la fruta ocupe buena parte de cada JPG guardado.
2. Calibrar el fondo vacío con `B` antes de pasar una fruta a la vez y anotar los rechazos, las pérdidas y los duplicados.
3. Registrar el identificador físico de cada fruta y la visibilidad de cada defecto por cámara; mantener los datos con personas fuera del repositorio público.
