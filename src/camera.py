"""Camera adapters used by the offline station 1 pipeline."""

import os

import cv2
from PIL import Image


class OpenCVCamera:
    def __init__(self, index, width, height):
        backends = ([cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
                    if os.name == "nt" else [cv2.CAP_V4L2, cv2.CAP_ANY])
        for backend in backends:
            capture = cv2.VideoCapture(index, backend)
            if capture.isOpened():
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                self.capture = capture
                return
            capture.release()
        raise RuntimeError(f"No se pudo abrir la camara OpenCV {index}")

    def read(self):
        return self.capture.read()

    def release(self):
        self.capture.release()

    def get(self, property_id):
        return self.capture.get(property_id)


class PiCamera2:
    def __init__(self, index, width, height):
        if not isinstance(index, int):
            raise RuntimeError("Picamera2 requiere un indice de camara numerico")
        try:
            from picamera2 import Picamera2 as Picamera2Library
        except ImportError as exc:
            raise RuntimeError("Picamera2 no esta instalado en esta Raspberry Pi") from exc
        self.capture = Picamera2Library(index)
        try:
            # RGB888 gives BGR byte order in Picamera2, as OpenCV expects.
            config = self.capture.create_video_configuration(
                main={"size": (width, height), "format": "RGB888"})
            self.capture.configure(config)
            self.capture.start()
        except Exception:
            self.capture.close()
            raise

    def read(self):
        frame = self.capture.capture_array("main")
        return frame is not None, frame

    def release(self):
        self.capture.stop()
        self.capture.close()


def open_camera(backend, index, width, height):
    if backend == "picamera2":
        return PiCamera2(index, width, height)
    if backend == "opencv":
        return OpenCVCamera(index, width, height)
    if backend == "auto":
        try:
            return OpenCVCamera(index, width, height)
        except RuntimeError as opencv_error:
            if os.name == "nt":
                raise
            try:
                return PiCamera2(index, width, height)
            except RuntimeError as picamera_error:
                raise RuntimeError(
                    f"OpenCV: {opencv_error}; Picamera2: {picamera_error}"
                ) from picamera_error
    raise ValueError(f"Backend de camara desconocido: {backend}")


def frame_to_image(frame):
    """Convierte BGR de OpenCV a RGB para el flujo de dos cámaras."""
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
