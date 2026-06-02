"""Text-to-speech — venture-agnostic narration generator.

Two providers wired via the platform tool router:
  - ElevenLabs (`tts_elevenlabs`): premium, natural-sounding voice. Default
    voice "Rachel" (warm, neutral US English); override via env or per-call.
  - OpenAI TTS-1-HD (`tts_openai`): fallback. Cheaper, less natural; fine
    for development and as a backup when ElevenLabs key is absent.

Both functions take plain script text + output dir and return
`{audio_path, duration_s, cost_usd, tool_used}`. They never block — when the
provider key is absent they return `audio_path=""` so callers can fall back
to a silent slideshow rather than crashing the pipeline.

ElevenLabs pricing (Starter tier, 2026): ~$5/mo for 30k characters. Per-call
cost is computed from character count using $0.30 / 1000 chars as a
conservative estimate so cost tracking is monotonic; replace with real
billing readout once the account is provisioned.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import requests


_ELEVENLABS_BASE     = "https://api.elevenlabs.io/v1"
_DEFAULT_EL_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"   # Rachel — neutral US English
_OPENAI_TTS_URL      = "https://api.openai.com/v1/audio/speech"

_COST_PER_1K_CHARS_ELEVEN = 0.30
_COST_PER_1K_CHARS_OPENAI = 0.015


def generate_tts(
    script: str,
    output_dir: str | Path = "./output",
    filename: Optional[str] = None,
    voice_id: Optional[str] = None,
    quality_tier: str = "standard",
) -> dict:
    """Route to the best active TTS tool for the requested tier.

    Tool selection is delegated to the platform tool router so wiring a
    new provider is one entry in `skills.json`.
    """
    from aiplatform.registry.tool_router import get_tool_function

    try:
        fn, tool_meta = get_tool_function("text-to-speech", tier=quality_tier)
    except Exception:
        return {"audio_path": "", "duration_s": 0.0, "cost_usd": 0.0,
                "tool_used": "", "error": "no active TTS tool"}

    result = fn(script=script, output_dir=output_dir, filename=filename, voice_id=voice_id)
    result.setdefault("tool_used", tool_meta["id"])
    return result


# ── ElevenLabs ────────────────────────────────────────────────────────────────

def tts_elevenlabs(
    script: str,
    output_dir: str | Path = "./output",
    filename: Optional[str] = None,
    voice_id: Optional[str] = None,
) -> dict:
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key or not (script or "").strip():
        return {"audio_path": "", "duration_s": 0.0, "cost_usd": 0.0,
                "tool_used": "elevenlabs",
                "error": "ELEVENLABS_API_KEY missing or empty script"}

    voice = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", _DEFAULT_EL_VOICE_ID)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (filename or "narration.mp3")

    try:
        resp = requests.post(
            f"{_ELEVENLABS_BASE}/text-to-speech/{voice}",
            headers={
                "xi-api-key":   api_key,
                "Accept":       "audio/mpeg",
                "Content-Type": "application/json",
            },
            json={
                "text":     script,
                "model_id": "eleven_turbo_v2_5",     # multilingual, low-latency
                "voice_settings": {
                    "stability":         0.55,
                    "similarity_boost":  0.75,
                    "style":             0.10,
                    "use_speaker_boost": True,
                },
            },
            timeout=180,
        )
    except requests.RequestException as exc:
        return {"audio_path": "", "duration_s": 0.0, "cost_usd": 0.0,
                "tool_used": "elevenlabs", "error": f"request error: {exc}"}

    if resp.status_code >= 300:
        return {"audio_path": "", "duration_s": 0.0, "cost_usd": 0.0,
                "tool_used": "elevenlabs",
                "error": f"elevenlabs {resp.status_code}: {resp.text[:300]}"}

    out_path.write_bytes(resp.content)
    chars = len(script)
    cost = round(chars * _COST_PER_1K_CHARS_ELEVEN / 1000.0, 4)
    return {
        "audio_path": str(out_path),
        "duration_s": _probe_duration(out_path),
        "cost_usd":   cost,
        "tool_used":  "elevenlabs",
        "chars":      chars,
    }


# ── OpenAI fallback ───────────────────────────────────────────────────────────

def tts_openai(
    script: str,
    output_dir: str | Path = "./output",
    filename: Optional[str] = None,
    voice_id: Optional[str] = None,
) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or not (script or "").strip():
        return {"audio_path": "", "duration_s": 0.0, "cost_usd": 0.0,
                "tool_used": "openai-tts",
                "error": "OPENAI_API_KEY missing or empty script"}

    voice = voice_id or os.environ.get("OPENAI_TTS_VOICE", "alloy")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (filename or "narration.mp3")

    try:
        resp = requests.post(
            _OPENAI_TTS_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type":  "application/json"},
            json={"model": "tts-1-hd", "voice": voice, "input": script, "format": "mp3"},
            timeout=120,
        )
    except requests.RequestException as exc:
        return {"audio_path": "", "duration_s": 0.0, "cost_usd": 0.0,
                "tool_used": "openai-tts", "error": f"request error: {exc}"}

    if resp.status_code >= 300:
        return {"audio_path": "", "duration_s": 0.0, "cost_usd": 0.0,
                "tool_used": "openai-tts",
                "error": f"openai {resp.status_code}: {resp.text[:300]}"}

    out_path.write_bytes(resp.content)
    chars = len(script)
    cost = round(chars * _COST_PER_1K_CHARS_OPENAI / 1000.0, 4)
    return {
        "audio_path": str(out_path),
        "duration_s": _probe_duration(out_path),
        "cost_usd":   cost,
        "tool_used":  "openai-tts",
        "chars":      chars,
    }


# ── Duration helper ───────────────────────────────────────────────────────────

def _probe_duration(audio_path: Path) -> float:
    """Use ffprobe when available; fall back to a char-count estimate."""
    try:
        import subprocess
        result = subprocess.run(
            [os.environ.get("FFPROBE_BINARY", "ffprobe"),
             "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, timeout=10,
        )
        return round(float(result.stdout.strip() or "0"), 2)
    except Exception:
        return 0.0
