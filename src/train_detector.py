"""Human review, grouped dataset export, training and independent test evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from PIL import Image
from .client_e2 import _atomic_bytes


def records(raw):
    for path in sorted(Path(raw).glob('*.json')):
        record=json.loads(path.read_text(encoding='utf-8'))
        if 'image' in record and 'fruit_group' in record:
            yield path,record


def review(raw):
    import cv2
    for path,record in records(raw):
        if record.get('reviewed'): continue
        frame=cv2.imread(str(path.parent/record['image']))
        if frame is None: raise ValueError(f'No se pudo leer {record["image"]}')
        title='Etiquetar: ENTER/SPACE confirma cuadro; ESC termina seleccion'
        # Scale only the GUI; annotation coordinates are stored at original size.
        scale=min(1,1000/frame.shape[1],700/frame.shape[0])
        preview=cv2.resize(frame,(round(frame.shape[1]*scale),round(frame.shape[0]*scale)))
        print(f'{record["fruit_group"]} {record["camera"]}: dibuja TODAS las naranjas visibles')
        selected=cv2.selectROIs(title,preview,showCrosshair=True,fromCenter=False)
        cv2.destroyAllWindows()
        if len(selected):
            answer=input('S: guardar cuadros / Q: salir / Enter: omitir: ').strip().lower()
            if answer=='q': return
            if answer!='s': continue
            width,height=frame.shape[1],frame.shape[0]
            record['boxes']=[[max(0,round(x/scale)),max(0,round(y/scale)),
                              min(width,round((x+w)/scale)),min(height,round((y+h)/scale))]
                             for x,y,w,h in selected if w>0 and h>0]
        else:
            answer=input('E: confirmar que NO hay naranjas / Q: salir / Enter: omitir: ').strip().lower()
            if answer=='q': return
            if answer!='e': continue
            record['boxes']=[]
        record['reviewed']=True
        _atomic_bytes(path,json.dumps(record,ensure_ascii=False,indent=2).encode('utf-8'))


def export_dataset(raw, destination):
    raw,destination=Path(raw),Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Usa una carpeta de dataset nueva para cada versión')
    samples=[(p,r) for p,r in records(raw) if r.get('reviewed') and isinstance(r.get('boxes'),list)]
    groups=sorted({r['fruit_group'] for _,r in samples},
                  key=lambda g:hashlib.sha256(g.encode()).hexdigest())
    if len(groups)<3:
        raise ValueError('Se necesitan al menos tres frutas físicas etiquetadas; eso solo permite probar el flujo, no demostrar precisión')
    split_path=raw/'group_splits.json'
    splits=json.loads(split_path.read_text(encoding='utf-8')) if split_path.exists() else {}
    if not splits:
        count=len(groups); validation=max(1,round(count*.15)); test=max(1,round(count*.15))
        splits={g:('val' if i<validation else 'test' if i<validation+test else 'train')
                for i,g in enumerate(groups)}
    for group in groups:
        if group not in splits:
            bucket=int(hashlib.sha256(group.encode()).hexdigest(),16)%100
            splits[group]='train' if bucket<70 else 'val' if bucket<85 else 'test'
    if {splits[g] for g in groups}!={'train','val','test'}:
        raise ValueError('Faltan frutas revisadas en alguno de los conjuntos persistidos')
    prepared=[]
    positives={split:0 for split in ('train','val','test')}
    for path,record in samples:
        image_path=path.parent/Path(record['image']).name
        with Image.open(image_path) as image: width,height=image.size
        lines=[]
        for x1,y1,x2,y2 in record['boxes']:
            if not (0<=x1<x2<=width and 0<=y1<y2<=height):
                raise ValueError(f'Cuadro inválido: {path}')
            lines.append(f'0 {(x1+x2)/2/width:.6f} {(y1+y2)/2/height:.6f} {(x2-x1)/width:.6f} {(y2-y1)/height:.6f}')
        split=splits[record['fruit_group']]
        positives[split]+=len(lines)
        prepared.append((path,record,image_path,split,lines))
    if any(v==0 for v in positives.values()):
        raise ValueError('Cada conjunto debe tener al menos una naranja anotada; añade más frutas')
    for path,record,image_path,split,lines in prepared:
        folder=destination/'images'/split; labels=destination/'labels'/split
        folder.mkdir(parents=True,exist_ok=True); labels.mkdir(parents=True,exist_ok=True)
        shutil.copy2(image_path,folder/image_path.name)
        (labels/(image_path.stem+'.txt')).write_text('\n'.join(lines),encoding='utf-8')
    config={'path':destination.resolve().as_posix(),'train':'images/train',
            'val':'images/val','test':'images/test','names':{0:'orange'}}
    _atomic_bytes(destination/'data.yaml',json.dumps(config,indent=2).encode('utf-8'))
    _atomic_bytes(destination/'provenance.json',json.dumps(
        [{'image':r['image'],'fruit_group':r['fruit_group'],'camera':r['camera'],'split':s}
         for _,r,_,s,_ in prepared],indent=2).encode('utf-8'))
    _atomic_bytes(split_path,json.dumps(splits,indent=2).encode('utf-8'))
    return destination/'data.yaml'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    label=sub.add_parser('label'); label.add_argument('--raw',type=Path,default=Path('dataset_naranjas/raw'))
    export=sub.add_parser('export'); export.add_argument('--raw',type=Path,default=Path('dataset_naranjas/raw'))
    export.add_argument('--destination',type=Path,required=True)
    for command in ('train','evaluate'):
        task=sub.add_parser(command); task.add_argument('--data',type=Path,required=True)
        task.add_argument('--model',type=Path,required=True)
        task.add_argument('--device',default='cpu')
        if command=='train':
            task.add_argument('--epochs',type=int,default=60)
            task.add_argument('--project',type=Path,default=Path('runs/naranjas'))
    args=parser.parse_args()
    if args.command=='label': review(args.raw)
    elif args.command=='export': print(export_dataset(args.raw,args.destination))
    else:
        if not args.model.is_file() or not args.data.is_file():
            raise ValueError('Se requiere modelo y dataset locales existentes')
        from ultralytics import YOLO
        model=YOLO(str(args.model))
        if args.command=='train':
            model.train(data=str(args.data),epochs=args.epochs,imgsz=640,batch=4,
                        device=args.device,project=str(args.project),name='detector',
                        seed=42,workers=0,patience=15)
        else:
            model.val(data=str(args.data),split='test',device=args.device,imgsz=640)


if __name__=='__main__': main()
