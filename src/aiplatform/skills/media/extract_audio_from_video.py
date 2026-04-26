"""
Platform skill: extract_audio_from_video

Extracts the audio track from a video file using FFmpeg, producing an MP3
suitable for Whisper transcription.

Venture-agnostic — never references any specific venture.
"""

import shutil
import subprocess
from pathlib import Path


class FFmpegNotInstalled(RuntimeError):
    pass


class UnsupportedVideoFormat(ValueError):
    pass


_SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


def extract_audio_from_video(
    video_path: str,
    output_path: str | None = None,
) -> dict:
    """
    Extract audio from a video file using FFmpeg.

    Args:
        video_path:   Absolute path to the video file.
        output_path:  Where to write the MP3. If omitted, writes alongside the
                      video file with a .mp3 extension.

    Returns:
        {
            "audio_path": str,   # absolute path to the extracted MP3
            "duration_seconds": float | None,
        }

    Raises:
        FFmpegNotInstalled:   if the `ffmpeg` binary cannot be found.
        UnsupportedVideoFormat: if the file extension is not in the supported set.
        RuntimeError:         if FFmpeg exits non-zero.
    """
    if shutil.which("ffmpeg") is None:
        raise FFmpegNotInstalled(
            "ffmpeg binary not found. "
            "Add 'ffmpeg' to nixpacks.toml [phases.setup] nixPkgs."
        )

    video = Path(video_path)
    ext = video.suffix.lower()
    if ext not in _SUPPORTED_VIDEO_EXTS:
        raise UnsupportedVideoFormat(
            f"Unsupported video format '{ext}'. "
            f"Accepted: {', '.join(sorted(_SUPPORTED_VIDEO_EXTS))}"
        )

    if output_path is None:
        output_path = str(video.with_suffix(".mp3"))

    cmd = [
        "ffmpeg",
        "-y",              # overwrite without prompting
        "-i", str(video),
        "-vn",             # drop video stream
        "-acodec", "libmp3lame",
        "-q:a", "2",       # VBR quality — good enough for Whisper
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )

    # Attempt to read duration from ffprobe (non-fatal if unavailable)
    duration_seconds: float | None = None
    if shutil.which("ffprobe"):
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                output_path,
            ],
            capture_output=True, text=True,
        )
        try:
            duration_seconds = float(probe.stdout.strip())
        except ValueError:
            pass

    return {
        "audio_path": output_path,
        "duration_seconds": duration_seconds,
    }
