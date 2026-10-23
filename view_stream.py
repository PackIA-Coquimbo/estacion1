import cv2
import sys

def main():
    print("Iniciando visualización de cámara...")
    print("Presiona la tecla 'q' en la ventana de video para salir.")

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: No se pudo abrir la cámara en el índice 0.")
        sys.exit(1)

    # Configuración de resolución sugerida (1280x720)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Cámara activa a resolución: {actual_w}x{actual_h}")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error al leer el fotograma.")
            break

        # Indicador de estado en pantalla
        cv2.putText(
            frame,
            f"Camara Activa ({actual_w}x{actual_h}) - Pulsa 'q' para salir",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
            cv2.LINE_AA
        )

        cv2.imshow("PackIACamara - Live Feed", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Visualización finalizada.")

if __name__ == "__main__":
    main()
