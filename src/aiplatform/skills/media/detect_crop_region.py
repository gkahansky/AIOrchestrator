"""
Platform skill: detect_crop_region

Analyses landscape video frames to find faces and compute the optimal horizontal
crop offset for portrait (9:16) transcoding, keeping subjects fully in frame.
Falls back to center crop when no faces are detected or OpenCV is unavailable.
Venture-agnostic.
"""

from pathlib import Path


def detect_crop_region(
    frame_paths: list[str],
    target_w: int = 1080,
    target_h: int = 1920,
) -> dict:
    """
    Compute the optimal portrait crop_x offset from landscape video frames.

    FFmpeg will scale the landscape clip so its height equals target_h (preserving
    aspect ratio), then crop target_w pixels starting at crop_x.  crop_x is in the
    coordinate space of that scaled image, not the original.

    Args:
        frame_paths:  Paths to landscape JPEG/PNG frames sampled from the clip.
        target_w:     Portrait crop width (default 1080).
        target_h:     Portrait crop height (default 1920).

    Returns:
        {
            "crop_x":     int | None,  # None means fall back to center crop
            "method":     "face_detection" | "center",
            "face_count": int,
        }
    """
    try:
        import cv2
    except ImportError:
        return {"crop_x": None, "method": "center", "face_count": 0}

    if not frame_paths:
        return {"crop_x": None, "method": "center", "face_count": 0}

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)

    face_centers_x: list[float] = []
    src_w = src_h = None

    for fp in frame_paths:
        if not Path(fp).exists():
            continue
        img = cv2.imread(str(fp))
        if img is None:
            continue
        h, w = img.shape[:2]
        if src_w is None:
            src_w, src_h = w, h
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30)
        )
        for (fx, fy, fw, fh) in faces:
            face_centers_x.append(fx + fw / 2)

    if src_w is None or src_h is None or not face_centers_x:
        return {"crop_x": None, "method": "center", "face_count": 0}

    # FFmpeg scales height to target_h while preserving aspect ratio.
    # Compute where faces land in that scaled image.
    scale = target_h / src_h
    scaled_w = int(src_w * scale)

    avg_x_scaled = (sum(face_centers_x) / len(face_centers_x)) * scale
    crop_x = int(avg_x_scaled - target_w / 2)
    crop_x = max(0, min(crop_x, scaled_w - target_w))

    return {
        "crop_x": crop_x,
        "method": "face_detection",
        "face_count": len(face_centers_x),
    }
