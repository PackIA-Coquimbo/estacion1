"""Detect and select two available webcams before starting paired capture."""

import subprocess
import sys

from .camera import open_camera


def camera_device_names() -> list[str]:
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError as exc:
        raise RuntimeError(
            "Falta PyGrabber para identificar las cámaras. "
            "Instala las dependencias con: python -m pip install -r requirements.txt"
        ) from exc
    return FilterGraph().get_input_devices()


def _has_frame(capture) -> bool:
    for _ in range(10):
        ok, frame = capture.read()
        if ok and frame is not None:
            return True
    return False


def discover_cameras() -> list[tuple[int, str]]:
    cameras = []
    failures = []
    # OpenCV's DirectShow indices follow this device enumeration order.
    for index, name in enumerate(camera_device_names()):
        capture = None
        try:
            capture = open_camera("opencv", index, 1280, 720)
            if _has_frame(capture):
                cameras.append((index, name))
            else:
                failures.append(f"{index}: {name} no entregó imagen")
        except RuntimeError as exc:
            failures.append(f"{index}: {name} ({exc})")
        finally:
            if capture is not None:
                capture.release()
    for failure in failures:
        print(f"No se pudo comprobar la cámara {failure}", file=sys.stderr)
    return cameras


def select_cameras(cameras: list[tuple[int, str]]) -> tuple[int, int]:
    if len(cameras) < 2:
        raise RuntimeError(
            f"Se detectaron {len(cameras)} cámaras; se necesitan al menos dos. "
            "Conecta las dos cámaras USB y cierra las aplicaciones que puedan usarlas."
        )
    if len(cameras) == 2:
        return cameras[0][0], cameras[1][0]

    print(
        f"Se detectaron {len(cameras)} cámaras. Elige las dos cámaras USB externas "
        "(excluye la integrada, si aparece):"
    )
    for index, name in cameras:
        print(f"  {index}: {name}")

    selected = []
    available_indices = [index for index, _ in cameras]
    for position in range(1, 3):
        while True:
            choice = input(f"Índice de la cámara USB externa {position}: ").strip()
            if (choice.isdecimal() and int(choice) in available_indices
                    and int(choice) not in selected):
                selected.append(int(choice))
                break
            print("Índice no válido; elige una cámara detectada distinta de la anterior.")
    return selected[0], selected[1]


def main() -> int:
    try:
        cameras = discover_cameras()
        if cameras:
            print("Cámaras detectadas:")
            for index, name in cameras:
                print(f"  {index}: {name}")
        else:
            print("Cámaras detectadas: ninguna")
        camera_1, camera_2 = select_cameras(cameras)
    except (RuntimeError, EOFError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    lot = input("ID del lote (ej. Prueba_001) [Prueba_001]: ").strip() or "Prueba_001"
    collect_training = '--collect-training' in sys.argv
    auto_mode = '' if collect_training else input("¿Captura automática al pasar la fruta? (S/N) [S]: ").strip()
    command = [
        sys.executable, "-m", "src.paired_capture",
        "--lot", lot,
        "--camera", str(camera_1),
        "--camera-2", str(camera_2),
    ]
    if not collect_training and auto_mode.lower() != "n":
        command.append("--auto")
    if collect_training:
        command.append('--collect-training')
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
