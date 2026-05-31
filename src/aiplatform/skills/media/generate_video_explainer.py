"""Scripted explainer video assembly — TTS narration + visual track + captions.

End-to-end:
  1. Caller supplies a script (already brand-voice-aware) and N visual cues.
  2. Each visual cue is either:
       - a local image path,
       - a public image / video URL (downloaded locally),
       - a Pexels search query (resolved + downloaded),
       - or a generated still via `generate_image` (Gemini Imagen / DALL-E).
  3. ElevenLabs TTS produces a single narration track (`media/tts.py`).
  4. ffprobe measures narration duration; visuals are time-allocated equally.
  5. FFmpeg builds a slideshow video at the target aspect ratio (9:16 reels,
     1:1 square, 16:9 long-form) with a slow Ken Burns zoom on each still
     and a match-cut transition between slides.
  6. Whisper-style SRT is built from `[start, end, text]` chunks of the script
     (one chunk per visual cue) and burned into the video as word-pop captions
     via the existing `burn_captions` skill.
  7. Returns `{video_path, duration_s, cost_usd, components: {...}}`.

This file is venture-agnostic. The content engine pipeline wires it up; other
ventures can call it too (e.g. content_repurposing for an audio-only podcast
clip with a static visual).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional


_DEFAULT_OUT_DIR = Path(os.environ.get("CE_VIDEO_OUT_DIR", "/tmp/content_engine_videos"))


# ── Aspect ratio presets ──────────────────────────────────────────────────────

_DIM = {
    "9:16":  (1080, 1920),
    "1:1":   (1080, 1080),
    "16:9":  (1920, 1080),
    "4:5":   (1080, 1350),
}


def generate_video_explainer(
    script: str,
    visuals: list[dict[str, Any]],
    *,
    aspect_ratio: str = "9:16",
    output_dir: str | Path | None = None,
    filename: Optional[str] = None,
    voice_id: Optional[str] = None,
    caption_style: str = "word_pop",
    fps: int = 30,
) -> dict[str, Any]:
    """Assemble a narrated explainer video.

    Args:
        script: full narration text. ElevenLabs converts → audio.
        visuals: list of visual cues, one per "scene". Each entry:
            {
              "kind":        "image" | "video" | "stock_query" | "generated",
              "value":       str (path/URL/query/prompt),
              "caption":     str (the chunk of the script said over this scene),
            }
        aspect_ratio: "9:16" | "1:1" | "16:9" | "4:5".
        caption_style: passed to `burn_captions` — "standard" or "word_pop".
    """
    if aspect_ratio not in _DIM:
        return _err(f"unsupported aspect_ratio '{aspect_ratio}'")
    if not visuals:
        return _err("no visuals supplied")
    if not (script or "").strip():
        return _err("script is empty")

    out_dir = Path(output_dir) if output_dir else _DEFAULT_OUT_DIR / uuid.uuid4().hex[:8]
    out_dir.mkdir(parents=True, exist_ok=True)
    final_path = out_dir / (filename or f"explainer_{aspect_ratio.replace(':', 'x')}.mp4")

    components: dict[str, Any] = {}
    cost_total = 0.0

    # 1. Narration ---------------------------------------------------------
    from aiplatform.skills.media.tts import generate_tts
    tts_res = generate_tts(script=script, output_dir=out_dir,
                           filename="narration.mp3", voice_id=voice_id)
    components["narration"] = tts_res
    cost_total += float(tts_res.get("cost_usd") or 0.0)
    narration_path = tts_res.get("audio_path") or ""
    narration_duration = float(tts_res.get("duration_s") or 0.0)
    if not narration_path:
        return _err(f"TTS failed: {tts_res.get('error', 'no audio')}",
                    components=components, cost=cost_total)

    # 2. Resolve visuals to local files -----------------------------------
    width, height = _DIM[aspect_ratio]
    local_visuals: list[dict] = []
    for i, cue in enumerate(visuals):
        local, cost = _resolve_visual_to_local(cue, i, out_dir, width, height,
                                               aspect_ratio)
        if not local:
            return _err(f"could not resolve visual #{i} (kind={cue.get('kind')})",
                        components=components, cost=cost_total)
        cost_total += cost
        local_visuals.append({**cue, "local_path": local})

    components["visuals"] = [{"kind": v["kind"], "local_path": v["local_path"]}
                             for v in local_visuals]

    # 3. Build slideshow video (visual-only, no audio) --------------------
    per_visual_seconds = max(2.0, round(narration_duration / len(local_visuals), 2)) \
                         if narration_duration > 0 else 4.0
    slideshow_path = out_dir / "slideshow.mp4"
    slideshow_err = _build_slideshow(
        visuals=local_visuals,
        per_visual_seconds=per_visual_seconds,
        width=width, height=height, fps=fps,
        out_path=slideshow_path,
    )
    if slideshow_err:
        return _err(slideshow_err, components=components, cost=cost_total)

    # 4. Mux narration over slideshow -------------------------------------
    muxed_path = out_dir / "muxed.mp4"
    mux_err = _mux_audio(slideshow_path, narration_path, muxed_path)
    if mux_err:
        return _err(mux_err, components=components, cost=cost_total)

    # 5. Burn captions ----------------------------------------------------
    srt = _build_srt_from_visuals(local_visuals, per_visual_seconds)
    if srt.strip():
        try:
            from aiplatform.skills.media.burn_captions import burn_captions
            burn_res = burn_captions(
                clip_path=str(muxed_path),
                srt_content=srt,
                output_path=str(final_path),
                style=caption_style,
                video_w=width,
                video_h=height,
            )
            components["captions"] = {"style": caption_style,
                                       "output": burn_res.get("captioned_path", str(final_path))}
        except Exception as exc:
            # Captions are quality-of-life, not load-bearing. If they fail
            # we ship the muxed video as the final output.
            shutil.copy2(muxed_path, final_path)
            components["captions"] = {"error": str(exc)}
    else:
        shutil.copy2(muxed_path, final_path)

    return {
        "video_path":   str(final_path),
        "duration_s":   narration_duration or (per_visual_seconds * len(local_visuals)),
        "aspect_ratio": aspect_ratio,
        "cost_usd":     round(cost_total, 4),
        "components":   components,
    }


# ── Visual resolution ────────────────────────────────────────────────────────

def _resolve_visual_to_local(
    cue: dict, index: int, out_dir: Path,
    width: int, height: int, aspect_ratio: str,
) -> tuple[str, float]:
    """Resolve a cue to a local file path. Returns (path, cost_usd)."""
    kind  = (cue.get("kind") or "").lower()
    value = cue.get("value", "")

    if kind == "image":
        if value and value.startswith(("http://", "https://")):
            return _download(value, out_dir / f"visual_{index}.jpg"), 0.0
        if value and Path(value).exists():
            return value, 0.0
        return "", 0.0

    if kind == "video":
        if value and value.startswith(("http://", "https://")):
            return _download(value, out_dir / f"visual_{index}.mp4"), 0.0
        if value and Path(value).exists():
            return value, 0.0
        return "", 0.0

    if kind == "stock_query":
        try:
            from aiplatform.skills.research.stock_media import (
                download_pexels_asset, search_pexels,
            )
        except ImportError:
            return "", 0.0
        orientation = "portrait" if aspect_ratio in {"9:16", "4:5"} else \
                      "square"   if aspect_ratio == "1:1" else "landscape"
        media_kind = cue.get("media", "photo")
        results = search_pexels(query=value, media=media_kind, per_page=3,
                                orientation=orientation).get("results", [])
        if not results:
            return "", 0.0
        ext = ".mp4" if media_kind == "video" else ".jpg"
        return download_pexels_asset(results[0]["url"],
                                     output_dir=out_dir,
                                     filename=f"visual_{index}{ext}"), 0.0

    if kind == "generated":
        try:
            from aiplatform.skills.media.generate_image import generate_image
        except ImportError:
            return "", 0.0
        result = generate_image(prompt=value, aspect_ratio=aspect_ratio,
                                quality_tier="standard",
                                output_dir=str(out_dir),
                                filename=f"visual_{index}.png")
        return result.get("image_path", ""), float(result.get("cost") or 0.0)

    return "", 0.0


def _download(url: str, dest: Path) -> str:
    """Stream a URL to local disk. Returns the path on success, else ''."""
    import requests
    try:
        resp = requests.get(url, timeout=60, stream=True)
        if resp.status_code >= 300:
            return ""
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    fh.write(chunk)
        return str(dest)
    except requests.RequestException:
        return ""


# ── Slideshow assembly ────────────────────────────────────────────────────────

def _build_slideshow(
    visuals: list[dict],
    per_visual_seconds: float,
    width: int, height: int, fps: int,
    out_path: Path,
) -> str:
    """Run FFmpeg to build a slideshow with Ken Burns motion on stills.

    Returns "" on success or an error string.
    """
    binary = os.environ.get("FFMPEG_BINARY", "ffmpeg")
    if not shutil.which(binary):
        return f"ffmpeg binary not found ('{binary}')"

    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        # Convert each visual to a uniform-duration mp4 clip.
        clip_paths: list[Path] = []
        for i, v in enumerate(visuals):
            clip_path = td_p / f"clip_{i:03d}.mp4"
            err = _visual_to_clip(v["local_path"], clip_path,
                                  per_visual_seconds, width, height, fps, binary)
            if err:
                return err
            clip_paths.append(clip_path)

        # Concat list.
        list_path = td_p / "list.txt"
        list_path.write_text("\n".join(f"file '{p}'" for p in clip_paths))

        cmd = [binary, "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
               "-c", "copy", str(out_path)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        except subprocess.CalledProcessError as exc:
            return f"concat ffmpeg failed: {exc.stderr.decode('utf-8', 'replace')[:400]}"
        except subprocess.TimeoutExpired:
            return "concat ffmpeg timed out"

    return ""


def _visual_to_clip(
    src: str, dest: Path,
    duration: float, width: int, height: int, fps: int, binary: str,
) -> str:
    """Render a single still or video into a fixed-duration mp4 with motion."""
    is_video = src.lower().endswith((".mp4", ".mov", ".webm", ".mkv"))

    if is_video:
        # Loop / trim video to target duration; rescale to canvas.
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,fps={fps}"
        )
        cmd = [
            binary, "-y", "-stream_loop", "-1", "-i", src,
            "-t", f"{duration:.2f}",
            "-vf", vf, "-an", "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "veryfast",
            str(dest),
        ]
    else:
        # Ken Burns zoom on a still. Total frames = duration * fps.
        total_frames = max(1, int(duration * fps))
        # Slow zoom from 1.0 → 1.10 over the clip.
        zoompan = (
            f"scale={width * 2}:{height * 2}:force_original_aspect_ratio=increase,"
            f"crop={width * 2}:{height * 2},"
            f"zoompan=z='min(zoom+0.001,1.10)':d={total_frames}:"
            f"s={width}x{height}:fps={fps}"
        )
        cmd = [
            binary, "-y", "-loop", "1", "-i", src, "-t", f"{duration:.2f}",
            "-vf", zoompan, "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "veryfast",
            str(dest),
        ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except subprocess.CalledProcessError as exc:
        return f"per-visual ffmpeg failed for {src}: " \
               f"{exc.stderr.decode('utf-8', 'replace')[:400]}"
    except subprocess.TimeoutExpired:
        return f"per-visual ffmpeg timed out for {src}"
    return ""


def _mux_audio(video_path: Path, audio_path: str, out_path: Path) -> str:
    binary = os.environ.get("FFMPEG_BINARY", "ffmpeg")
    cmd = [
        binary, "-y", "-i", str(video_path), "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(out_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except subprocess.CalledProcessError as exc:
        return f"mux ffmpeg failed: {exc.stderr.decode('utf-8', 'replace')[:400]}"
    except subprocess.TimeoutExpired:
        return "mux ffmpeg timed out"
    return ""


# ── SRT from cue captions ────────────────────────────────────────────────────

def _build_srt_from_visuals(visuals: list[dict], per_visual_seconds: float) -> str:
    def _fmt(s: float) -> str:
        h = int(s // 3600)
        m = int((s % 3600) // 60)
        sec = int(s % 60)
        ms = int((s - int(s)) * 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    lines: list[str] = []
    idx = 1
    cursor = 0.0
    for v in visuals:
        text = (v.get("caption") or "").strip()
        start, end = cursor, cursor + per_visual_seconds
        cursor = end
        if not text:
            continue
        lines.extend([str(idx), f"{_fmt(start)} --> {_fmt(end)}", text, ""])
        idx += 1
    return "\n".join(lines)


# ── Error helper ─────────────────────────────────────────────────────────────

def _err(message: str, *, components: dict | None = None, cost: float = 0.0) -> dict:
    return {
        "video_path": "",
        "duration_s": 0.0,
        "cost_usd":   round(cost, 4),
        "components": components or {},
        "error":      message,
    }
