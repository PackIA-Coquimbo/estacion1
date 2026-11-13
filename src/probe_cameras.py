"""Comprueba índices y resolución real de varias cámaras en un solo PC."""

import argparse
import json

from .camera import open_camera


def main() -> int:
    parser = argparse.ArgumentParser(description="Comprobar cámaras USB de estación 1")
    parser.add_argument("indices", nargs="*", type=int, default=[0, 1],
                        help="Índices a abrir al mismo tiempo (por defecto 0 1)")
    args = parser.parse_args()
    if len(set(args.indices)) != len(args.indices):
        parser.error("No repitas un índice de cámara")
    captures = {}
    try:
        errors = []
        for index in args.indices:
            try:
                captures[index] = open_camera("opencv", index, 1280, 720)
            except RuntimeError as exc:
                errors.append(str(exc))
        results = []
        for index, capture in captures.items():
            ok = False
            frame = None
            for _ in range(10):
                ok, frame = capture.read()
                if ok and frame is not None:
                    break
            if not ok or frame is None:
                errors.append(f"La cámara {index} abrió, pero no entregó imagen")
                continue
            height, width = frame.shape[:2]
            results.append({"indice": index, "ancho_captura_px": width,
                            "alto_captura_px": height})
        print(json.dumps({"camaras": results, "errores": errors},
                         ensure_ascii=False, indent=2))
        return 1 if errors else 0
    finally:
        for capture in captures.values():
            capture.release()


if __name__ == "__main__":
    raise SystemExit(main())
