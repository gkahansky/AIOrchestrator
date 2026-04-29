"""
Platform skill: burn_captions

Hardens subtitle captions into a video clip using FFmpeg's ass filter.
Writes an ASS file with explicit PlayResX/PlayResY so FontSize is in literal pixels
(avoids the PlayResY=288 default scaling that makes fonts 6x too large on portrait 1920px video).
Venture-agnostic.
"""

import os
import re
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


def _srt_ts_to_ass(ts: str) -> str:
    """Convert SRT timestamp to ASS centisecond format: '00:00:10,500' → '0:00:10.50'"""
    ts = ts.strip().replace(",", ".")
    h, m, s_ms = ts.split(":")
    s, ms = s_ms.split(".")
    cs = int(ms.ljust(3, "0")[:3]) // 10   # normalise to ms then to centiseconds
    return f"{int(h)}:{int(m):02d}:{int(s):02d}.{cs:02d}"


def _hex_color(name: str) -> str:
    """Convert common colour names to BGR hex for ASS style (format: BBGGRR)."""
    _map = {
        "white":  "FFFFFF",
        "black":  "000000",
        "yellow": "00FFFF",   # ASS BGR: yellow = 00FFFF
        "red":    "0000FF",
        "blue":   "FF0000",
    }
    if name.lower() in _map:
        return _map[name.lower()]
    name = name.lstrip("#")
    if len(name) == 6:
        r, g, b = name[0:2], name[2:4], name[4:6]
        return b + g + r
    return "FFFFFF"


def _build_ass(
    srt_content: str,
    video_w: int,
    video_h: int,
    font_size: int,
    font_color: str,
    border_color: str,
    border_width: int,
) -> str:
    """
    Convert SRT content to an ASS script with explicit PlayRes dimensions.
    FontSize is in literal pixels relative to video_h — no libass default scaling.
    """
    primary = f"&H00{_hex_color(font_color)}"
    outline  = f"&H00{_hex_color(border_color)}"
    # Push captions 4% up from the bottom edge
    margin_v = max(40, int(video_h * 0.04))

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {video_w}\n"
        f"PlayResY: {video_h}\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,{font_size},{primary},&H000000FF,{outline},&H00000000,"
        f"-1,0,0,0,100,100,0,0,1,{border_width},0,2,10,10,{margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    lines = [header]
    blocks = re.split(r"\n\s*\n", srt_content.strip())
    for block in blocks:
        parts = block.strip().split("\n")
        if len(parts) < 3:
            continue
        ts_line = parts[1]
        if " --> " not in ts_line:
            continue
        start_str, end_str = ts_line.split(" --> ", 1)
        text = " ".join(parts[2:]).strip().replace("\n", "\\N")
        try:
            start_ass = _srt_ts_to_ass(start_str)
            end_ass   = _srt_ts_to_ass(end_str)
        except Exception:
            continue
        lines.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}\n")

    return "".join(lines)


def _build_word_pop_srt(srt_content: str, words_per_chunk: int = 2) -> str:
    """
    Split each SRT segment into small word chunks with evenly divided timing.
    Produces the TikTok-style word-pop caption effect.
    """
    def _ts_to_s(ts: str) -> float:
        h, m, s_ms = ts.strip().split(":")
        s, ms = s_ms.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    def _s_to_ts(s: float) -> str:
        s = max(0.0, s)
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        ms = int(round((s - int(s)) * 1000))
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    blocks = re.split(r"\n\s*\n", srt_content.strip())
    result: list[str] = []
    idx = 1

    for block in blocks:
        parts = block.strip().split("\n")
        if len(parts) < 3:
            continue
        ts_line = parts[1]
        if " --> " not in ts_line:
            continue
        start_str, end_str = ts_line.split(" --> ", 1)
        text = " ".join(parts[2:]).strip()
        words = text.split()
        if not words:
            continue

        start_s = _ts_to_s(start_str)
        end_s = _ts_to_s(end_str)
        duration = max(0.05, end_s - start_s)

        chunks = [words[i:i + words_per_chunk] for i in range(0, len(words), words_per_chunk)]
        chunk_dur = duration / len(chunks)

        for j, chunk_words in enumerate(chunks):
            cs = start_s + j * chunk_dur
            ce = cs + chunk_dur
            result.append(
                f"{idx}\n{_s_to_ts(cs)} --> {_s_to_ts(ce)}\n{' '.join(chunk_words).upper()}\n"
            )
            idx += 1

    return "\n".join(result)


def burn_captions(
    clip_path: str,
    srt_content: str,
    output_path: str | None = None,
    font_size: int = 64,
    font_color: str = "white",
    border_color: str = "black",
    border_width: int = 3,
    video_w: int = 1080,
    video_h: int = 1920,
    style: str = "standard",
) -> dict:
    """
    Burn hardcoded captions into a video clip via an ASS file.

    Args:
        clip_path:    Path to source clip (already transcoded to target format).
        srt_content:  SRT string with timestamps relative to clip start (0-based).
        output_path:  Where to write. Defaults to <stem>_captioned.mp4.
        font_size:    Caption font size in pixels (relative to video_h via PlayResY).
        font_color:   Caption text colour.
        border_color: Text border colour.
        border_width: Border width in pixels.
        video_w:      Video width — must match the actual clip (default 1080 for 9:16 portrait).
        video_h:      Video height — must match the actual clip (default 1920 for 9:16 portrait).
        style:        "standard" (phrase-level captions) or "word_pop" (2-word TikTok chunks,
                      large yellow text — overrides font_size/color/border_width).

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

    if style == "word_pop":
        srt_content = _build_word_pop_srt(srt_content, words_per_chunk=2)
        font_size   = 90
        font_color  = "yellow"
        border_width = 4

    ass_content = _build_ass(srt_content, video_w, video_h, font_size, font_color, border_color, border_width)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False, encoding="utf-8") as ass_file:
        ass_file.write(ass_content)
        ass_path = ass_file.name

    try:
        # Forward slashes work on both Linux (Railway) and Windows dev
        ass_escaped = ass_path.replace("\\", "/")
        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(clip),
            "-vf", f"ass={ass_escaped}",
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "fast",
            "-c:a", "copy",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg caption burn failed (exit {result.returncode}):\n{result.stderr[-3000:]}"
            )
    finally:
        Path(ass_path).unlink(missing_ok=True)

    return {"captioned_path": output_path}
