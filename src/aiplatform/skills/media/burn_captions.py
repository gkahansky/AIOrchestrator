"""
Platform skill: burn_captions

Hardens subtitle captions into a video clip using FFmpeg's subtitles filter.
Takes an SRT string (with timestamps relative to clip start = 0).
Venture-agnostic.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def build_srt_for_clip(
    segments: list[dict],
    clip_start_s: float,
    clip_end_s: float,
) -> str:
    """
    Build an SRT string from Whisper segments that fall within [clip_start_s, clip_end_s].
    Timestamps are re-zeroed relative to clip_start_s.
    """
    def _fmt(s: float) -> str:
        s = max(0.0, s)
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        ms = int((s - int(s)) * 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    srt_lines = []
    idx = 1
    for seg in segments:
        seg_start = float(seg["start"])
        seg_end = float(seg["end"])
        # Include if segment overlaps the clip window
        if seg_end <= clip_start_s or seg_start >= clip_end_s:
            continue
        rel_start = max(0.0, seg_start - clip_start_s)
        rel_end = min(clip_end_s - clip_start_s, seg_end - clip_start_s)
        srt_lines.append(str(idx))
        srt_lines.append(f"{_fmt(rel_start)} --> {_fmt(rel_end)}")
        srt_lines.append(seg["text"].strip())
        srt_lines.append("")
        idx += 1

    return "\n".join(srt_lines)


def burn_captions(
    clip_path: str,
    srt_content: str,
    output_path: str | None = None,
    font_size: int = 48,
    font_color: str = "white",
    border_color: str = "black",
    border_width: int = 2,
) -> dict:
    """
    Burn hardcoded captions into a video clip.

    Args:
        clip_path:    Path to source clip (already transcoded to target format).
        srt_content:  SRT string with timestamps relative to clip start (0-based).
        output_path:  Where to write. Defaults to <stem>_captioned.mp4.
        font_size:    Subtitle font size in pixels.
        font_color:   Subtitle text colour (FFmpeg colour name or hex).
        border_color: Text border/shadow colour.
        border_width: Border width in pixels.

    Returns:
        {"captioned_path": str}

    Raises:
        RuntimeError: if FFmpeg exits non-zero.
    """
    ffmpeg_bin = os.getenv("FFMPEG_BINARY", "ffmpeg")
    if shutil.which(ffmpeg_bin) is None:
        raise RuntimeError(f"FFmpeg binary '{ffmpeg_bin}' not found.")

    clip = Path(clip_path)
    if output_path is None:
        output_path = str(clip.parent / f"{clip.stem}_captioned.mp4")

    # Write SRT to a temp file (FFmpeg subtitles filter requires a file path)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False, encoding="utf-8") as srt_file:
        srt_file.write(srt_content)
        srt_path = srt_file.name

    try:
        # Escape path for FFmpeg filter (Windows backslashes need escaping)
        srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
        vf = (
            f"subtitles='{srt_escaped}':"
            f"force_style='FontSize={font_size},"
            f"PrimaryColour=&H00{_hex_color(font_color)},"
            f"OutlineColour=&H00{_hex_color(border_color)},"
            f"Outline={border_width},"
            f"Alignment=2'"       # 2 = bottom-center
        )
        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(clip),
            "-vf", vf,
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "fast",
            "-c:a", "copy",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg caption burn failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
            )
    finally:
        Path(srt_path).unlink(missing_ok=True)

    return {"captioned_path": output_path}


def _hex_color(name: str) -> str:
    """Convert common colour names to BGR hex for ASS/FFmpeg style."""
    _map = {
        "white": "FFFFFF",
        "black": "000000",
        "yellow": "00FFFF",
        "red": "0000FF",
        "blue": "FF0000",
    }
    if name.lower() in _map:
        return _map[name.lower()]
    # If already hex (#RRGGBB), convert to BGR
    name = name.lstrip("#")
    if len(name) == 6:
        r, g, b = name[0:2], name[2:4], name[4:6]
        return b + g + r
    return "FFFFFF"
