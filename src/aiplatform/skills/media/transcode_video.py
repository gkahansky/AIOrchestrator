"""
Platform skill: transcode_video

Re-encodes a video clip to a target aspect ratio using FFmpeg.
Default: portrait 9:16 (1080×1920) for social media reels/shorts.
Venture-agnostic.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


_FORMATS = {
    "portrait_9_16":   {"w": 1080, "h": 1920},
    "landscape_16_9":  {"w": 1920, "h": 1080},
    "square_1_1":      {"w": 1080, "h": 1080},
}


def transcode_video(
    clip_path: str,
    target_format: str = "portrait_9_16",
    output_path: str | None = None,
    crf: int = 23,
    crop_x: int | None = None,
    crop_timeline: list[tuple[float, int]] | None = None,
) -> dict:
    """
    Re-encode a video clip to the target aspect ratio.

    For portrait 9:16: scales landscape footage to target height then crops to
    target width.  crop_timeline (from detect_crop_timeline) drives a dynamic
    FFmpeg sendcmd filter that updates crop_x at each timestamp, keeping the
    active speaker in frame throughout the clip.  Falls back to static crop_x
    (from detect_crop_region) or center crop when neither is provided.

    Args:
        clip_path:      Path to source clip (from extract_video_segment).
        target_format:  "portrait_9_16" | "landscape_16_9" | "square_1_1"
        output_path:    Where to write. Defaults to <stem>_<format>.mp4.
        crf:            H.264 quality (18 = near-lossless, 28 = small file). Default 23.
        crop_x:         Static horizontal crop offset (legacy / fallback).
        crop_timeline:  Dynamic crop — list of (t_seconds, crop_x) from detect_crop_timeline.
                        Takes priority over crop_x when provided.

    Returns:
        {"transcoded_path": str, "width": int, "height": int}

    Raises:
        ValueError:   if target_format is unknown.
        RuntimeError: if FFmpeg exits non-zero.
    """
    if target_format not in _FORMATS:
        raise ValueError(f"Unknown target_format '{target_format}'. Valid: {list(_FORMATS)}")

    ffmpeg_bin = os.getenv("FFMPEG_BINARY", "ffmpeg")
    if shutil.which(ffmpeg_bin) is None:
        raise RuntimeError(
            f"FFmpeg binary '{ffmpeg_bin}' not found. Set FFMPEG_BINARY env var."
        )

    fmt = _FORMATS[target_format]
    w, h = fmt["w"], fmt["h"]

    clip = Path(clip_path)
    if output_path is None:
        output_path = str(clip.parent / f"{clip.stem}_{target_format}.mp4")

    cmds_file: str | None = None
    try:
        if crop_timeline:
            # Dynamic crop via sendcmd: write timestamped crop_x changes to a temp file.
            # FFmpeg sendcmd updates the crop filter's x param at each listed time.
            fd, cmds_file = tempfile.mkstemp(suffix=".txt", prefix="crop_cmds_")
            with os.fdopen(fd, "w") as f:
                for t, cx in crop_timeline:
                    f.write(f"{t} crop x {cx};\n")
            # Initial crop_x = first timeline value so frame 0 starts correctly
            initial_cx = crop_timeline[0][1]
            vf = (
                f"scale=-2:{h}:flags=lanczos,"
                f"crop={w}:{h}:{initial_cx}:0,"
                f"sendcmd=f='{cmds_file}'"
            )
        elif crop_x is not None:
            # Static face-detected crop (legacy path)
            vf = f"scale=-2:{h}:flags=lanczos,crop={w}:{h}:{crop_x}:0"
        else:
            # Default center crop
            vf = (
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h}"
            )

        cmd = [
            ffmpeg_bin, "-y",
            "-i", str(clip),
            "-vf", vf,
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FFmpeg transcode failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
            )
    finally:
        if cmds_file and os.path.exists(cmds_file):
            os.unlink(cmds_file)

    return {"transcoded_path": output_path, "width": w, "height": h}
