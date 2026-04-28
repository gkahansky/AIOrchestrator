"""
Platform skill: extract_video_segments

Extracts a time-bounded segment from a video file using FFmpeg.
Venture-agnostic.
"""

import os
import shutil
import subprocess
from pathlib import Path


class FFmpegNotInstalled(RuntimeError):
    pass


def extract_video_segment(
    video_path: str,
    start_s: float,
    end_s: float,
    output_path: str | None = None,
) -> dict:
    """
    Extract a video segment [start_s, end_s] using FFmpeg stream copy (fast, no re-encode).

    Args:
        video_path:   Absolute path to the source video.
        start_s:      Start time in seconds.
        end_s:        End time in seconds. Must be > start_s.
        output_path:  Where to write the output. Defaults to <video_stem>_clip_<start>.mp4.

    Returns:
        {"clip_path": str, "duration_s": float}

    Raises:
        FFmpegNotInstalled: if ffmpeg binary not found.
        ValueError:         if start_s >= end_s.
        RuntimeError:       if FFmpeg exits non-zero.
    """
    if start_s >= end_s:
        raise ValueError(f"start_s ({start_s}) must be less than end_s ({end_s})")

    ffmpeg_bin = os.getenv("FFMPEG_BINARY", "ffmpeg")
    if shutil.which(ffmpeg_bin) is None:
        raise FFmpegNotInstalled(
            f"FFmpeg binary '{ffmpeg_bin}' not found. "
            "Railway: ffmpeg is installed via Dockerfile apt-get. "
            "Local: run 'choco install ffmpeg' or set FFMPEG_BINARY env var."
        )

    video = Path(video_path)
    if output_path is None:
        output_path = str(video.parent / f"{video.stem}_seg_{int(start_s)}.mp4")

    duration = end_s - start_s
    cmd = [
        ffmpeg_bin, "-y",
        "-ss", str(start_s),
        "-i", str(video),
        "-t", str(duration),
        "-c", "copy",           # stream copy — fast, no quality loss
        "-avoid_negative_ts", "make_zero",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg segment extraction failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )

    return {"clip_path": output_path, "duration_s": duration}
