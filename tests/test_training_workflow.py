import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from src.train_detector import export_dataset
from src.training_samples import save_samples
from src.detector import PositionResult
from src.image_quality import QualityResult


class TrainingTests(unittest.TestCase):
    def test_capture_requires_human_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            paths=save_samples({'camara_1':Image.new('RGB',(1280,720))},'F1','L1',
                {'camara_1':(QualityResult(False,('imagen_borrosa',),{}),
                             PositionResult(False,'yolo','fruta_ausente',{}))},root)
            record=json.loads(paths[0].with_suffix('.json').read_text(encoding='utf-8'))
            self.assertFalse(record['reviewed']); self.assertIsNone(record['boxes'])
            self.assertEqual(record['fruit_group'],'L1__F1')
            with self.assertRaises(ValueError): export_dataset(root,root/'dataset')

    def test_split_groups_both_cameras_and_is_persistent(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); raw=root/'raw'; raw.mkdir()
            for fruit in range(10):
                for camera in ('camara_0','camara_1'):
                    name=f'f{fruit}_{camera}'
                    Image.new('RGB',(640,480)).save(raw/(name+'.png'))
                    (raw/(name+'.json')).write_text(json.dumps({'image':name+'.png',
                        'fruit_group':f'fruit_{fruit}','camera':camera,'reviewed':True,
                        'boxes':[[200,100,400,300]]}),encoding='utf-8')
            # Unreviewed failed detections must not become negative training labels.
            (raw/'unknown.json').write_text(json.dumps({'image':'missing.png','fruit_group':'unknown',
                'reviewed':False,'boxes':None}),encoding='utf-8')
            export_dataset(raw,root/'v1')
            provenance=json.loads((root/'v1/provenance.json').read_text(encoding='utf-8'))
            for fruit in {r['fruit_group'] for r in provenance}:
                self.assertEqual(len({r['split'] for r in provenance if r['fruit_group']==fruit}),1)
            self.assertEqual({r['split'] for r in provenance},{'train','val','test'})
            self.assertEqual(len(provenance),20)
            export_dataset(raw,root/'v2')
            self.assertEqual((root/'v1/provenance.json').read_bytes(),(root/'v2/provenance.json').read_bytes())
            with self.assertRaises(ValueError): export_dataset(raw,root/'v1')


if __name__=='__main__': unittest.main()
