"""
Platform skill: add_watermark

Overlays a text watermark on a video clip using FFmpeg drawtext filter.
Only applied when plan == "free". All other plans pass the clip through unchanged.
Venture-agnostic.
"""

import os
import shutil
import subprocess
from pathlib import Path


def add_watermark(
    clip_path: str,
    plan: str,
    watermark_text: str = "ECHOFORGE",
    output_path: str | None = None,
) -> dict:
    """
    Apply a text watermark overlay if plan is "free". Otherwise returns the
    original clip path unchanged (no FFmpeg call, no copy).

    Args:
        clip_path:       Path to source clip.
        plan:            Customer plan ("free" | "starter" | "pro" | "studio").
        watermark_text:  Text to overlay. Default: "ECHOFORGE".
        output_path:     Where to write watermarked clip. Only used when plan=="free".

    Returns:
        {"final_path": str, "watermarked": bool}
    """
    if plan != "free":
        return {"final_path": clip_path, "watermarked": False}

    ffmpeg_bin = os.getenv("FFMPEG_BINARY", "ffmpeg")
    if shutil.which(ffmpeg_bin) is None:
        raise RuntimeError(f"FFmpeg binary '{ffmpeg_bin}' not found.")

    clip = Path(clip_path)
    if output_path is None:
        output_path = str(clip.parent / f"{clip.stem}_watermarked.mp4")

    # Top-right watermark, semi-transparent white text with dark border
    vf = (
        f"drawtext=text='{watermark_text}':"
        f"fontsize=36:"
        f"fontcolor=white@0.7:"
        f"bordercolor=black@0.5:"
        f"borderw=2:"
        f"x=w-tw-20:"
        f"y=20"
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
            f"FFmpeg watermark failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
        )

    return {"final_path": output_path, "watermarked": True}
