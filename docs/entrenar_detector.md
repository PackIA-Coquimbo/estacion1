# Guía de recolección, etiquetado y entrenamiento del detector

Este documento describe el flujo implementado en [`src/training_samples.py`](../src/training_samples.py) y [`src/train_detector.py`](../src/train_detector.py).

## 1. Recolectar muestras reales

Ejecuta `recolectar_ejemplos.bat` (o `python -m src.paired_capture --collect-training ...`):
- Pulsa **`T`** para guardar fotogramas originales `.png` + `.json` de ambas cámaras en `dataset_naranjas/raw/`.
- Pulsa **`N`** únicamente cuando cambies a una nueva naranja física, de modo que todas las vistas de una misma fruta conserven el mismo `fruit_group`.

## 2. Etiquetado humano

```powershell
.\.venv\Scripts\python.exe -m src.train_detector label --raw dataset_naranjas/raw
```

- Dibuja todas las naranjas visibles en cada imagen (`ENTER`/`SPACE` confirma cuadro, `ESC` termina selección).
- Confirma con `S` para guardar cuadros, o `E` si la imagen no contiene naranjas (ejemplo negativo).
- Solo los registros marcados con `reviewed: true` se exportan al dataset.

## 3. Exportación agrupada por fruta física

```powershell
.\.venv\Scripts\python.exe -m src.train_detector export --raw dataset_naranjas/raw --destination dataset_naranjas/v1
```

- Mantiene todas las vistas y cámaras de una misma `fruit_group` en el mismo split (`train`, `val` o `test`) para evitar fugas entre conjuntos.
- Persiste las asignaciones en `dataset_naranjas/raw/group_splits.json` para versiones futuras y exige al menos 3 frutas físicas etiquetadas con positivos en los tres splits.

## 4. Entrenamiento y evaluación

```powershell
.\.venv\Scripts\python.exe -m src.train_detector train --data dataset_naranjas/v1/data.yaml --model models/yolov8n.pt --epochs 60
.\.venv\Scripts\python.exe -m src.train_detector evaluate --data dataset_naranjas/v1/data.yaml --model runs/naranjas/detector/weights/best.pt
```

Los pesos entrenados no reemplazan automáticamente a `models/yolov8n.pt`; evalúalos antes con `--yolo-model`.
