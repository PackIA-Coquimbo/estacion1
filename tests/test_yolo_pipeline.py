from pathlib import Path
import unittest
import tempfile
import numpy as np
from PIL import Image, ImageFilter
from src.config import CaptureConfig
from src.yolo_detector import YoloOrangeDetector
from src.image_quality import quality_for_position
from src.output_image import prepare_output
from src.paired_capture import process_capture


class Boxes:
    def __init__(self, rows): self.rows=rows; self.data=self
    def cpu(self): return self
    def numpy(self): return np.asarray(self.rows)


class YoloTests(unittest.TestCase):
    def test_third_search_recovers_fruit_at_original_coordinates(self):
        detector=self.detector([])
        calls=[]
        class Model:
            def predict(self,source,**kwargs):
                calls.append(source.size)
                rows=[] if len(calls)<3 else [[150,100,450,330,.7,49]]
                return [type('Result',(),{'boxes':Boxes(rows)})()]
        detector.model=Model()
        position=detector(Image.new('RGB',(1280,720)),None,CaptureConfig())
        self.assertEqual(len(calls),3)
        self.assertTrue(position.correct)
        self.assertEqual(position.subject_bounds,(482,244,782,474))

    def test_retry_recovers_small_fruit_and_maps_original_coordinates(self):
        detector=self.detector([])
        calls=[]
        class Model:
            def predict(self,source,**kwargs):
                calls.append(source.size)
                rows=[[500,220,780,500,.3,49]] if len(calls)==1 else [[300,150,580,430,.8,49]]
                return [type('Result',(),{'boxes':Boxes(rows)})()]
        detector.model=Model()
        position=detector(Image.new('RGB',(1280,720)),None,CaptureConfig())
        self.assertTrue(position.correct)
        self.assertTrue(position.metrics['reintento_zona'])
        self.assertEqual(position.subject_bounds,(492,222,772,502))
        self.assertLess(calls[1][0],calls[0][0])

    def test_camera_specific_threshold_does_not_accept_low_confidence(self):
        detector=self.detector([[500,220,780,500,.6,49]])
        position=detector(Image.new('RGB',(1280,720)),None,CaptureConfig(yolo_confidence=.7))
        self.assertFalse(position.correct)
        self.assertEqual(position.reason,'confianza_yolo_baja')
        self.assertEqual(position.metrics['umbral_yolo'],.7)

    def detector(self, rows):
        detector=object.__new__(YoloOrangeDetector)
        detector.confidence=0.55; detector.orange_ids=[49]
        class Model:
            def predict(self,*args,**kwargs):
                return [type('Result',(),{'boxes':Boxes(rows)})()]
        detector.model=Model()
        return detector

    def test_rejects_absence_multiple_and_frame_edge(self):
        image=Image.new('RGB',(1280,720)); config=CaptureConfig(roi=(0,0,1,1))
        for rows,reason in (([], 'fruta_ausente'),
                            ([[500,200,780,500,.9,49],[700,200,900,500,.8,49]],'varias_frutas_en_zona'),
                            ([[0,200,280,500,.9,49]],'fruta_cortada_en_borde')):
            position=self.detector(rows)(image,None,config)
            self.assertFalse(position.correct); self.assertEqual(position.reason,reason)

    def test_blurry_fruit_is_not_rescued_by_sharp_background(self):
        rng=np.random.default_rng(4)
        array=rng.integers(40,220,(720,1280,3),dtype=np.uint8)
        image=Image.fromarray(array)
        image.paste(image.crop((500,220,780,500)).filter(ImageFilter.GaussianBlur(10)),(500,220))
        position=self.detector([[500,220,780,500,.9,49]])(image,None,CaptureConfig())
        quality=quality_for_position(image,CaptureConfig(),position)
        self.assertIn('imagen_borrosa',quality.reasons)

    def test_tight_crop_excludes_distant_background(self):
        image=Image.new('RGB',(1280,720),'blue'); image.paste('orange',(500,220,780,500))
        output,mode,box=prepare_output(image,(500,220,780,500),CaptureConfig().roi,'fruit')
        self.assertEqual(output.size,(480,640)); self.assertEqual(mode,'fruit')
        self.assertEqual(box,(478,198,802,522))
        self.assertEqual(output.getpixel((240,320)),(255,165,0))

    def test_blurry_view_is_kept_out_of_outbox(self):
        rng=np.random.default_rng(9)
        image=Image.fromarray(rng.integers(40,220,(720,1280,3),dtype=np.uint8))
        detector=self.detector([[500,220,780,500,.9,49]])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            accepted,photos,_=process_capture({'camara_0':image},'L1','F1',
                {'camara_0':CaptureConfig()},root/'out',root/'bad',
                position_detector=detector,output_framing='fruit')
            self.assertEqual(accepted['estado_captura'],'aceptada')
            with Image.open(photos['camara_0']) as saved: self.assertEqual(saved.size,(480,640))
            rejected,_,_=process_capture({'camara_0':image.filter(ImageFilter.GaussianBlur(10))},
                'L1','F1',{'camara_0':CaptureConfig()},root/'out',root/'bad',
                position_detector=detector,output_framing='fruit')
            self.assertNotEqual(rejected['estado_captura'],'aceptada')
            self.assertEqual(len(list((root/'out').rglob('*.json'))),1)


if __name__=='__main__': unittest.main()
