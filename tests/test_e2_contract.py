"""Run the unmodified upstream listener with a fake classifier, real JPEG/ACK."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from src.send_e2 import drain
from src.client_e2 import publish
from PIL import Image

tree = ast.parse((Path(__file__).parent / 'fixtures' / 'e2_station_listener_reference.py').read_text(encoding='utf-8'))
# Only isolate the two actual upstream protocol classes; no model dependencies.
nodes = [n for n in tree.body if isinstance(n,ast.ClassDef) and n.name in ('StationCommunicator','StationListener')]
namespace = {}
exec('from pathlib import Path\nfrom typing import *\nimport time,json,os,cv2,numpy as np\nHAS_OPENCV=True\nQualityPredictor=object',namespace)
exec(compile(ast.Module(body=nodes,type_ignores=[]),'upstream_e2','exec'),namespace)
class Predictor:
    def predict_cv2(self, frame):
        assert frame.shape == (640,480,3)
        return {'predicted_class':'buen_estado','confidence_percent':80,
                'probabilities':{'buen_estado':0.8,'mal_estado':0.1,'marginalmente_buena':0.1},
                'latency_preprocess_ms':1,'latency_inference_ms':1},None

class ContractTests(unittest.TestCase):
    def test_upstream_listener(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); out=root/'out'; channel=root/'shm'
            for index in range(2):
                publish({'camara_0':Image.new('RGB',(480,640),(180,100,30)),
                         'camara_1':Image.new('RGB',(480,640),(170,100,30))},
                        {'id_lote':'L1','id_fruta':'F1','id_captura':f'captura_{index}',
                         'id_rafaga':'R1','indice_rafaga':index+1,'estado_captura':'aceptada',
                         'vistas':[{'camara':'camara_0','metodo_posicion':'yolo'},
                                   {'camara':'camara_1','metodo_posicion':'yolo'}]},out)
            listener=namespace['StationListener'](Predictor(),channel)
            stop=threading.Event()
            def listen():
                while not stop.wait(0.001): listener.process_pending_event()
            thread=threading.Thread(target=listen); thread.start()
            try:
                assert drain(out,channel)==4
                assert drain(out,channel)==0
                assert len(list((out/'.e2_receipts').glob('*.json')))==4
                assert listener.processed_count==4
            finally: stop.set(); thread.join()
            print('PASS upstream listener: four views, same fruit, ACK, no duplicate delivery')
            # New channel without listener must preserve pending JPEG on timeout.
            channel2=root/'silent'; out2=root/'out2'
            publish({'camara_0':Image.new('RGB',(480,640))},
                    {'id_lote':'L2','id_fruta':'F2','id_captura':'C2','estado_captura':'aceptada',
                     'vistas':[{'camara':'camara_0','metodo_posicion':'yolo'}]},out2)
            try: drain(out2,channel2,0.03)
            except TimeoutError: pass
            else: raise AssertionError('Missing timeout')
            assert (channel2/'estacion_trigger.flag').exists()
            assert (channel2/'estacion1_pending.json').exists()
            assert not list((out2/'.e2_receipts').glob('*.json'))
            print('PASS timeout preserves pending image')
