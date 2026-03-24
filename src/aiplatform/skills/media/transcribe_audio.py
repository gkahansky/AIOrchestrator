"""
Skill: transcribe_audio
Transcribe an audio file using OpenAI Whisper and extract raw timing segments.

Input:
    audio_path (str | Path): Path to the audio file (mp3/mp4/wav/m4a/ogg/webm)
    language   (str):        Optional ISO-639-1 language code. Default: "en"

Output:
    {
        "transcript":       str,        # Full transcript text
        "segments":         list[dict], # [{start, end, text}, ...] — Whisper segments
        "timestamps_raw":   str,        # Pre-formatted "[MM:SS] text" — one line per segment
        "duration_seconds": float,
        "cost_usd":         float,      # Based on whisper-1 pricing
        "language":         str,
    }
"""

import os
from pathlib import Path
from typing import Optional

from openai import OpenAI


COST_PER_MINUTE = 0.006  # whisper-1: $0.006/min


def transcribe_audio(
    audio_path: str | Path,
    language: Optional[str] = "en",
) -> dict:
    """
    Transcribe an audio file using OpenAI Whisper.
    Returns full transcript, timing segments, and cost.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language=language,
            response_format="verbose_json",
        )

    segments = [
        {"start": seg.start, "end": seg.end, "text": seg.text.strip()}
        for seg in (response.segments or [])
    ]

    timestamps_raw = "\n".join(
        f"[{_fmt_time(seg['start'])}] {seg['text']}"
        for seg in segments
    )

    duration = float(response.duration or 0)
    cost_usd = round((duration / 60) * COST_PER_MINUTE, 4)

    return {
        "transcript": response.text,
        "segments": segments,
        "timestamps_raw": timestamps_raw,
        "duration_seconds": duration,
        "cost_usd": cost_usd,
        "language": response.language or language,
    }


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"
