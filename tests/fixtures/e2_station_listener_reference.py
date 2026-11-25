"""Reference E2 listener protocol fixture matching estacion2 (JPEG -> trigger -> result -> ACK)."""

from pathlib import Path
from typing import Any
import json
import os
import time
import cv2
import numpy as np

HAS_OPENCV = True
QualityPredictor = object


class StationCommunicator:
    """Shared-folder protocol helper for Station 2 listener."""

    def __init__(self, shm_dir: Path):
        self.shm_dir = Path(shm_dir)
        self.shm_dir.mkdir(parents=True, exist_ok=True)
        self.frame_path = self.shm_dir / "estacion_frame.jpg"
        self.trigger_path = self.shm_dir / "estacion_trigger.flag"
        self.ack_path = self.shm_dir / "estacion_ack.flag"
        self.result_path = self.shm_dir / "estacion2_result.json"

    def write_result(self, payload: dict[str, Any]) -> None:
        tmp = self.result_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.result_path)

    def send_ack(self) -> None:
        tmp = self.ack_path.with_suffix(".flag.tmp")
        tmp.write_text(str(time.time()), encoding="ascii")
        os.replace(tmp, self.ack_path)


class StationListener:
    """Consume pending JPEG events and write classification results + ACK."""

    def __init__(self, predictor: Any, shm_dir: Path):
        self.predictor = predictor
        self.comm = StationCommunicator(shm_dir)
        self.processed_count = 0

    def process_pending_event(self) -> bool:
        if not self.comm.trigger_path.exists() or not self.comm.frame_path.exists():
            return False
        frame = cv2.imread(str(self.comm.frame_path))
        if frame is None:
            return False
        result, _ = self.predictor.predict_cv2(frame)
        payload = {"station_id": 2, **result}
        self.comm.write_result(payload)
        self.comm.trigger_path.unlink(missing_ok=True)
        self.comm.send_ack()
        self.processed_count += 1
        return True
