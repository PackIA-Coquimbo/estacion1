"""Save original frames for human annotation, separately from accepted E2 images."""
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4
from .client_e2 import safe_id, _atomic_bytes


def save_samples(images, fruit_id, lot_id, results, root):
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    group=safe_id(lot_id)+'__'+safe_id(fruit_id)
    sample_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'_'+uuid4().hex[:6]
    paths=[]
    for camera,image in images.items():
        stem=sample_id+'_'+safe_id(camera)
        path=root/(stem+'.png')
        image.save(path)
        quality,position=results[camera]
        record={'image':path.name,'fruit_group':group,'camera':camera,
                'reviewed':False,'boxes':None,'suggested_box':position.subject_bounds,
                'reasons':list(quality.reasons)+([position.reason] if position.reason else []),
                'detection_metrics':position.metrics,'quality_metrics':quality.metrics}
        _atomic_bytes(path.with_suffix('.json'),json.dumps(record,ensure_ascii=False,indent=2).encode('utf-8'))
        paths.append(path)
    return paths
