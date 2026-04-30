"""
Platform skill: detect_crop_region

Analyses landscape video frames to find faces and compute the optimal horizontal
crop offset for portrait (9:16) transcoding, keeping subjects fully in frame.
Falls back to center crop when no faces are detected or OpenCV is unavailable.
Venture-agnostic.

Two public functions:
  detect_crop_region(frame_paths)     — one crop_x from pre-extracted frames (legacy)
  detect_crop_timeline(video_path)    — per-2s dynamic crop_x via inline FFmpeg extraction
"""

import os
import subprocess
import tempfile
from pathlib import Path
from statistics import median


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


def detect_crop_timeline(
    video_path: str,
    target_w: int = 1080,
    target_h: int = 1920,
    sample_interval_s: float = 1.0,
) -> dict:
    """
    Build a per-timestamp crop_x timeline from a landscape video clip.

    Extracts one frame every sample_interval_s seconds using FFmpeg, detects
    faces in each frame, and collapses the data into stable speaker regions.
    Each region has a single fixed crop_x; transitions are instant cuts (≥300px
    shift sustained for ≥2s).  This produces clean jump-cuts between speakers
    rather than a gradual pan across the frame.

    Args:
        video_path:        Path to landscape source video.
        target_w:          Portrait crop width (default 1080).
        target_h:          Portrait crop height (default 1920).
        sample_interval_s: Seconds between face-detection samples (default 1).

    Returns:
        {
            "timeline": [(t_seconds, crop_x), ...],   # empty → use center crop
            "method":   "face_tracking" | "center",
            "face_count": int,
        }
    """
    try:
        import cv2
    except ImportError:
        return {"timeline": [], "method": "center", "face_count": 0}

    ffmpeg_bin = os.getenv("FFMPEG_BINARY", "ffmpeg")

    # ── 1. Extract one frame per interval into a temp dir ────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        frame_pattern = os.path.join(tmp, "f%04d.jpg")
        cmd = [
            ffmpeg_bin, "-y",
            "-i", video_path,
            "-vf", f"fps=1/{sample_interval_s},scale=-2:720",
            "-q:v", "4",
            frame_pattern,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            return {"timeline": [], "method": "center", "face_count": 0}

        frame_files = sorted(Path(tmp).glob("f*.jpg"))
        if not frame_files:
            return {"timeline": [], "method": "center", "face_count": 0}

        frontal_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        profile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_profileface.xml"
        )

        # ── 2. Detect faces per frame; track active speaker ──────────────────
        raw: list[tuple[float, int | None]] = []   # (t_seconds, crop_x | None)
        src_w = src_h = None
        total_faces = 0
        last_cx: int | None = None
        prev_gray = None   # previous frame for motion-based speaker detection

        for idx, fp in enumerate(frame_files):
            t = idx * sample_interval_s
            img = cv2.imread(str(fp))
            if img is None:
                raw.append((t, None))
                prev_gray = None
                continue
            h, w = img.shape[:2]
            if src_w is None:
                src_w, src_h = w, h
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Try frontal first; fall back to profile cascade if nothing found
            faces = frontal_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30)
            )
            if len(faces) == 0:
                faces = profile_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30)
                )

            if len(faces) == 0:
                raw.append((t, None))
                prev_gray = gray
                continue

            total_faces += len(faces)
            scale = target_h / src_h
            scaled_w = int(src_w * scale)

            if len(faces) == 1:
                # Single face — straightforward
                fx, fy, fw, fh = faces[0]
                best_cx = int((fx + fw / 2) * scale - target_w / 2)
                best_cx = max(0, min(best_cx, scaled_w - target_w))

            elif prev_gray is not None:
                # Multiple faces: find the active speaker via motion.
                # The speaking side of the frame shows more pixel change
                # (mouth movement) than the listening side.
                # Split the frame at the midpoint and compare motion per half.
                mid = w // 2
                diff = cv2.absdiff(gray, prev_gray).astype(float)
                left_motion  = float(diff[:, :mid].mean())
                right_motion = float(diff[:, mid:].mean())

                # Sort faces left-to-right
                sorted_faces = sorted(faces, key=lambda f: f[0])
                left_face  = sorted_faces[0]
                right_face = sorted_faces[-1]

                # Clear winner threshold: one side must have 20% more motion
                if left_motion > right_motion * 1.2:
                    chosen = left_face
                elif right_motion > left_motion * 1.2:
                    chosen = right_face
                else:
                    # No clear speaker — prefer continuity with previous crop
                    chosen = min(
                        faces,
                        key=lambda f: abs(
                            int((f[0] + f[2] / 2) * scale - target_w / 2) - (last_cx or scaled_w // 2)
                        ),
                    )

                fx, fy, fw, fh = chosen
                best_cx = int((fx + fw / 2) * scale - target_w / 2)
                best_cx = max(0, min(best_cx, scaled_w - target_w))

            else:
                # Multiple faces, no previous frame for motion: prefer continuity
                chosen = min(
                    faces,
                    key=lambda f: abs(
                        int((f[0] + f[2] / 2) * scale - target_w / 2) - (last_cx or scaled_w // 2)
                    ),
                )
                fx, fy, fw, fh = chosen
                best_cx = int((fx + fw / 2) * scale - target_w / 2)
                best_cx = max(0, min(best_cx, scaled_w - target_w))

            last_cx = best_cx
            prev_gray = gray
            raw.append((t, best_cx))

    if total_faces == 0:
        return {"timeline": [], "method": "center", "face_count": 0}

    # ── 3. Fill None gaps: carry forward last known value (or center fallback) ─
    if src_w is None or src_h is None:
        return {"timeline": [], "method": "center", "face_count": 0}

    scale = target_h / src_h
    scaled_w = int(src_w * scale)
    center_x = max(0, (scaled_w - target_w) // 2)

    filled: list[tuple[float, int]] = []
    last_cx = center_x
    for (t, cx) in raw:
        val = cx if cx is not None else last_cx
        filled.append((t, val))
        last_cx = val

    # ── 4. Rolling median smoothing (window = 3) ─────────────────────────────
    smoothed: list[tuple[float, int]] = []
    for i, (t, _) in enumerate(filled):
        window = [filled[j][1] for j in range(max(0, i - 1), min(len(filled), i + 2))]
        smoothed.append((t, int(median(window))))

    # ── 5. Collapse into stable speaker regions ───────────────────────────────
    # A region ends when crop_x shifts by ≥300px (true speaker switch).
    # Within a region all samples are averaged to a single fixed crop_x so the
    # FFmpeg expression produces instant cuts, not a gradual pan.
    # The 300px threshold tolerates normal head-movement jitter (~150px) while
    # reliably catching left↔right speaker transitions (typically 800–1500px).
    REGION_SHIFT = 300
    MIN_REGION_FRAMES = max(1, int(2.0 / sample_interval_s))  # ≥2s before committing

    regions: list[tuple[float, int]] = []   # (start_t, median_cx)
    region_start_idx = 0
    region_vals: list[int] = [smoothed[0][1]]

    for i in range(1, len(smoothed)):
        t, cx = smoothed[i]
        current_median = int(median(region_vals))
        if abs(cx - current_median) >= REGION_SHIFT:
            # Commit current region only if it's long enough
            if (i - region_start_idx) >= MIN_REGION_FRAMES:
                regions.append((smoothed[region_start_idx][0], int(median(region_vals))))
            else:
                # Short region — merge into the new one by discarding it
                pass
            region_start_idx = i
            region_vals = [cx]
        else:
            region_vals.append(cx)

    # Commit final region
    regions.append((smoothed[region_start_idx][0], int(median(region_vals))))

    return {"timeline": regions, "method": "face_tracking", "face_count": total_faces}
