"""
Platform skill: extract_video_frames

Extracts N evenly-spaced frames from a video clip as JPEG images.
Used as input for thumbnail frame scoring.
Venture-agnostic.
"""

import os
import shutil
import subprocess
from pathlib import Path


def extract_video_frames(
    clip_path: str,
    n: int = 10,
    output_dir: str | None = None,
) -> dict:
    """
    Extract N evenly-spaced frames from a video clip.

    Args:
        clip_path:   Path to the video clip.
        n:           Number of frames to extract (default 10).
        output_dir:  Directory to write frames. Defaults to <clip_dir>/frames/.

    Returns:
        {"frame_paths": List[str]}   — sorted by frame index.

    Raises:
        RuntimeError: if FFmpeg exits non-zero.
    """
    ffmpeg_bin = os.getenv("FFMPEG_BINARY", "ffmpeg")
    if shutil.which(ffmpeg_bin) is None:
        raise RuntimeError(f"FFmpeg binary '{ffmpeg_bin}' not found.")

    clip = Path(clip_path)
    if output_dir is None:
        output_dir = str(clip.parent / "frames")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Extract N frames evenly spaced: fps = N / duration
    # We use select filter + vsync to get exactly N frames
    out_pattern = str(Path(output_dir) / f"{clip.stem}_frame_%03d.jpg")

    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(clip),
        "-vf", f"select='not(mod(n,max(1,trunc(nb_frames/{n}))))',scale=1280:720",
        "-fps_mode", "vfr",   # replaces deprecated -vsync vfr (FFmpeg 5+)
        "-frames:v", str(n),
        "-q:v", "2",
        out_pattern,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg frame extraction failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )

    frame_paths = sorted(
        str(p) for p in Path(output_dir).glob(f"{clip.stem}_frame_*.jpg")
    )
    return {"frame_paths": frame_paths}
