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
    # Input-side -ss is a fast keyframe seek: FFmpeg starts at the nearest keyframe
    # BEFORE start_s, so the clip may begin a few seconds earlier than requested.
    # We omit -avoid_negative_ts so packet PTS is preserved from the source — this
    # lets us probe the actual clip start below. transcode_video re-encodes (resetting
    # PTS to 0) so source-relative PTS in the raw clip causes no downstream issue.
    cmd = [
        ffmpeg_bin, "-y",
        "-ss", str(start_s),
        "-i", str(video),
        "-t", str(duration),
        "-c", "copy",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg segment extraction failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )

    # Probe the actual first video packet PTS to find the true clip start.
    # Because we skipped -avoid_negative_ts, PTS reflects the source video time
    # of the keyframe FFmpeg actually snapped to (may differ from start_s by 0-5s).
    actual_start_s = start_s  # safe fallback
    ffprobe_bin = os.getenv("FFPROBE_BINARY", "ffprobe")
    try:
        probe = subprocess.run(
            [
                ffprobe_bin, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "packet=pts_time",
                "-read_intervals", "%+#1",
                "-of", "csv=p=0",
                output_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        if probe.returncode == 0 and probe.stdout.strip():
            first_pts = probe.stdout.strip().split("\n")[0].strip()
            if first_pts and first_pts != "N/A":
                actual_start_s = float(first_pts)
    except Exception:
        pass  # fallback to requested start_s — captions may be slightly off

    return {
        "clip_path": output_path,
        "duration_s": duration,
        "actual_start_s": actual_start_s,
    }
