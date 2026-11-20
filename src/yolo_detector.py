"""Local orange detection. Model confidence is not a fruit quality label."""
from pathlib import Path
import numpy as np
from .detector import PositionResult


class YoloOrangeDetector:
    def __init__(self, model_path, confidence=0.55):
        if not Path(model_path).is_file():
            raise RuntimeError(f"Falta el modelo local: {model_path}")
        from ultralytics import YOLO
        self.model = YOLO(str(model_path))
        self.confidence = confidence
        self.orange_ids = [i for i, name in self.model.names.items()
                           if name.lower() in {'orange', 'naranja'}]
        if not self.orange_ids:
            raise RuntimeError("El modelo debe incluir la clase orange")

    def __call__(self, image, reference, config, manual_confirmed=False):
        confidence_limit = getattr(config, 'yolo_confidence', None) or self.confidence
        candidates = []
        rx1, ry1, rx2, ry2 = config.roi
        best_confidence = 0.0
        def detect(source, offset=(0,0), crop=False):
            nonlocal best_confidence
            result = self.model.predict(source, classes=self.orange_ids,
                                        conf=min(0.15,confidence_limit), imgsz=640, verbose=False)[0]
            found = []
            for row in result.boxes.data.cpu().numpy():
                x1,y1,x2,y2,confidence,_ = row
                # A cropped retry must contain the complete detected box.
                if crop and min(x1,y1,source.width-x2,source.height-y2) < 5:
                    continue
                x1,x2 = x1+offset[0],x2+offset[0]
                y1,y2 = y1+offset[1],y2+offset[1]
                cx,cy = (x1+x2)/2/image.width,(y1+y2)/2/image.height
                if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
                    best_confidence = max(best_confidence,float(confidence))
                    if confidence >= confidence_limit:
                        found.append((tuple(int(v) for v in (x1,y1,x2,y2)),float(confidence)))
            return found
        candidates = detect(image)
        retried = False
        if not candidates:
            # Improve the effective resolution of smaller lateral fruit, without
            # lowering the acceptance threshold or treating apples as oranges.
            left,top = max(0,int((rx1-.10)*image.width)),max(0,int((ry1-.10)*image.height))
            right,bottom = min(image.width,int((rx2+.10)*image.width)),min(image.height,int((ry2+.10)*image.height))
            candidates = detect(image.crop((left,top,right,bottom)),(left,top),True)
            retried = True
        if not candidates:
            gx1,gy1,gx2,gy2=config.guide_roi
            left,top=max(0,int((gx1-.10)*image.width)),max(0,int((gy1-.05)*image.height))
            right,bottom=min(image.width,int((gx2+.10)*image.width)),min(image.height,int((gy2+.05)*image.height))
            candidates=detect(image.crop((left,top,right,bottom)),(left,top),True)
        if len(candidates) != 1:
            reason = ('confianza_yolo_baja' if best_confidence else 'fruta_ausente') if not candidates else 'varias_frutas_en_zona'
            return PositionResult(False, 'yolo', reason,
                                  {'frutas_detectadas':len(candidates),'mejor_confianza_yolo':round(best_confidence,4),
                                   'umbral_yolo':confidence_limit,'reintento_zona':retried})
        bounds, confidence = candidates[0]
        x1,y1,x2,y2 = bounds
        reason = None
        if min(x1,y1,image.width-x2,image.height-y2) < 5:
            reason = 'fruta_cortada_en_borde'
        elif x2-x1 < config.min_subject_width or y2-y1 < config.min_subject_height:
            reason = 'fruta_demasiado_pequena'
        return PositionResult(reason is None, 'yolo', reason,
                              {'confianza_yolo': round(confidence,4), 'frutas_detectadas': 1,
                               'umbral_yolo':confidence_limit,'reintento_zona':retried,
                               'ancho_fruta_px': x2-x1, 'alto_fruta_px': y2-y1}, bounds)
