"""Detect and select two available webcams before starting paired capture."""

import subprocess
import sys

from .camera import open_camera


MAX_CAMERA_INDEX = 10


def _has_frame(capture) -> bool:
    for _ in range(10):
        ok, frame = capture.read()
        if ok and frame is not None:
            return True
    return False


def discover_cameras() -> list[int]:
    cameras = []
    for index in range(MAX_CAMERA_INDEX):
        capture = None
        try:
            capture = open_camera("opencv", index, 1280, 720)
            if _has_frame(capture):
                cameras.append(index)
        except RuntimeError:
            pass
        finally:
            if capture is not None:
                capture.release()
    return cameras


def select_cameras(cameras: list[int]) -> tuple[int, int]:
    if len(cameras) < 2:
        raise RuntimeError(
            f"Se detectaron {len(cameras)} cámaras; se necesitan al menos dos. "
            "Conecta las dos cámaras USB y cierra las aplicaciones que puedan usarlas."
        )
    if len(cameras) == 2:
        return cameras[0], cameras[1]

    print(
        f"Se detectaron {len(cameras)} cámaras. Elige las dos cámaras USB externas "
        "(excluye la integrada, si aparece):"
    )
    for index in cameras:
        print(f"  {index}: cámara detectada (índice OpenCV)")

    selected = []
    for position in range(1, 3):
        while True:
            choice = input(f"Índice de la cámara USB externa {position}: ").strip()
            if choice.isdecimal() and int(choice) in cameras and int(choice) not in selected:
                selected.append(int(choice))
                break
            print("Índice no válido; elige una cámara detectada distinta de la anterior.")
    return selected[0], selected[1]


def main() -> int:
    try:
        cameras = discover_cameras()
        print(f"Índices de cámaras detectadas: {', '.join(map(str, cameras)) or 'ninguno'}")
        camera_1, camera_2 = select_cameras(cameras)
    except (RuntimeError, EOFError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    lot = input("ID del lote (ej. Prueba_001) [Prueba_001]: ").strip() or "Prueba_001"
    auto_mode = input("¿Captura automática al pasar la fruta? (S/N) [N]: ").strip()
    command = [
        sys.executable, "-m", "src.paired_capture",
        "--lot", lot,
        "--camera", str(camera_1),
        "--camera-2", str(camera_2),
    ]
    if auto_mode.lower() == "s":
        command.append("--auto")
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
