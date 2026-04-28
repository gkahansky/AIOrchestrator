"""
Platform skill: extract_video_frames

Extracts N evenly-spaced frames from a video clip as JPEG images.
Used as input for thumbnail frame scoring.
Venture-agnostic.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path


def _probe_duration(ffprobe_bin: str, clip_path: str) -> float:
    """Return clip duration in seconds via ffprobe, fallback to 60s."""
    probe = subprocess.run(
        [
            ffprobe_bin, "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "json",
            clip_path,
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(json.loads(probe.stdout)["format"]["duration"])
    except Exception:
        return 60.0


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
    ffmpeg_bin  = os.getenv("FFMPEG_BINARY", "ffmpeg")
    ffprobe_bin = os.getenv("FFPROBE_BINARY", "ffprobe")

    if shutil.which(ffmpeg_bin) is None:
        raise RuntimeError(f"FFmpeg binary '{ffmpeg_bin}' not found.")

    clip = Path(clip_path)
    if output_dir is None:
        output_dir = str(clip.parent / "frames")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    duration = _probe_duration(ffprobe_bin, str(clip))
    safe_dur = max(duration, 1.0)

    out_pattern = str(Path(output_dir) / f"{clip.stem}_frame_%03d.jpg")

    # fps=N/duration → N evenly-spaced frames regardless of stream metadata.
    # scale=-2:720  → maintain aspect ratio at 720px height (works for portrait and landscape).
    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(clip),
        "-vf", f"fps={n}/{safe_dur},scale=-2:720",
        "-frames:v", str(n),
        "-q:v", "2",
        out_pattern,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg frame extraction failed (exit {result.returncode}):\n"
            f"{result.stderr[-4000:]}"
        )

    frame_paths = sorted(
        str(p) for p in Path(output_dir).glob(f"{clip.stem}_frame_*.jpg")
    )
    return {"frame_paths": frame_paths}
