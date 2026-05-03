"""
Platform skill: transcode_video

Re-encodes a video clip to a target aspect ratio using FFmpeg.
Default: portrait 9:16 (1080×1920) for social media reels/shorts.
Venture-agnostic.
"""

import os
import shutil
import subprocess
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

    if crop_timeline:
        # Dynamic crop via FFmpeg expression: builds a step-function if(lt(t,...)) chain.
        # This is more portable than sendcmd (which requires filter command support).
        cx_expr = _build_crop_x_expr(crop_timeline)
        vf = f"scale=-2:{h}:flags=lanczos,crop={w}:{h}:{cx_expr}:0"
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

    return {"transcoded_path": output_path, "width": w, "height": h}


def _compress_timeline(
    timeline: list[tuple[float, int]],
    change_threshold: int = 50,
) -> list[tuple[float, int]]:
    """
    Drop timeline entries whose crop_x didn't change enough to matter.

    detect_crop_timeline already returns stable region boundaries (300px shift
    threshold), so this is primarily a safety net against any residual duplicates.
    The default 50px threshold removes genuine no-ops while keeping all speaker
    transitions, preventing FFmpeg expression length overflows on long clips.
    """
    if not timeline:
        return timeline
    compressed = [timeline[0]]
    for t, cx in timeline[1:]:
        if abs(cx - compressed[-1][1]) >= change_threshold:
            compressed.append((t, cx))
    return compressed


_PAN_DURATION_S = 0.4  # seconds for the linear crop pan at each speaker transition


def _build_crop_x_expr(timeline: list[tuple[float, int]]) -> str:
    """
    Build an FFmpeg crop x expression from a crop timeline.

    Compresses the timeline first, then produces a nested if(lt(t,T),CX,...) chain
    with a short linear ramp at each speaker transition instead of an instant step cut.
    The ramp runs for _PAN_DURATION_S (0.4 s) or half the gap to the next switch,
    whichever is shorter, keeping subjects smoothly in frame rather than jumping.

    Commas inside expressions are escaped as \\, (FFmpeg filter graph syntax).
    """
    timeline = _compress_timeline(timeline)
    if len(timeline) == 1:
        return str(timeline[0][1])

    # Build right-to-left: innermost expression is the final crop_x value
    expr = str(timeline[-1][1])
    for i in range(len(timeline) - 2, -1, -1):
        t_switch = timeline[i + 1][0]
        cx_from  = timeline[i][1]
        cx_to    = timeline[i + 1][1]

        # Cap pan at half the gap to the following transition (if any)
        if i + 2 < len(timeline):
            gap = timeline[i + 2][0] - t_switch
        else:
            gap = _PAN_DURATION_S * 4
        pan = min(_PAN_DURATION_S, gap / 2)
        t_end = t_switch + pan

        if pan < 0.05 or cx_from == cx_to:
            # Trivially short gap or no movement — use a plain step
            expr = f"if(lt(t\\,{t_switch:.3f})\\,{cx_from}\\,{expr})"
        else:
            delta = cx_to - cx_from
            # Linear interpolation: cx_from + delta*(t-t_switch)/pan
            lerp = f"({cx_from}+({delta})*(t-{t_switch:.3f})/{pan:.3f})"
            expr = (
                f"if(lt(t\\,{t_switch:.3f})\\,{cx_from}\\,"
                f"if(lt(t\\,{t_end:.3f})\\,{lerp}\\,{expr}))"
            )
    return expr
