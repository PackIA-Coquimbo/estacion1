import os
import sys
import json
import time

def test_camera():
    try:
        import cv2
        import numpy as np
    except ImportError:
        print(json.dumps({"error": "opencv-python not installed"}))
        sys.exit(1)

    results = {
        "status": "unknown",
        "cameras_found": [],
        "errors": []
    }

    # Test camera indices 0 through 3
    found_any = False
    for idx in range(3):
        # On Windows, cv2.CAP_DSHOW provides fast and reliable DirectShow initialization
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            # Try default backend if DSHOW fails
            cap = cv2.VideoCapture(idx)

        if cap.isOpened():
            # Warm up camera sensor for auto-exposure/auto-focus
            success = False
            frame = None
            for _ in range(8):
                ret, temp_frame = cap.read()
                if ret and temp_frame is not None:
                    success = True
                    frame = temp_frame
                time.sleep(0.05)

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            cam_info = {
                "index": idx,
                "opened": True,
                "width": width,
                "height": height,
                "fps": fps,
                "frame_captured": success
            }

            if success and frame is not None:
                # Calculate basic image statistics
                mean_brightness = float(np.mean(frame))
                std_brightness = float(np.std(frame))
                cam_info["mean_brightness"] = round(mean_brightness, 2)
                cam_info["std_brightness"] = round(std_brightness, 2)
                cam_info["shape"] = list(frame.shape)

                # Save snapshot to verify
                os.makedirs("captures", exist_ok=True)
                snapshot_path = f"captures/test_camera_{idx}.jpg"
                cv2.imwrite(snapshot_path, frame)
                cam_info["snapshot_saved"] = snapshot_path

                found_any = True

            cap.release()
            results["cameras_found"].append(cam_info)
        else:
            cap.release()

    if found_any:
        results["status"] = "SUCCESS"
    elif results["cameras_found"]:
        results["status"] = "CAMERA_DETECTED_NO_FRAME"
    else:
        results["status"] = "NO_CAMERA_ACCESSIBLE"

    print(json.dumps(results, indent=2))
    return 0 if found_any else 1

if __name__ == "__main__":
    sys.exit(test_camera())
