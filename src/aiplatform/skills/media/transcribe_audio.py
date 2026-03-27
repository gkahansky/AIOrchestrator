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
import tempfile
from pathlib import Path
from typing import Optional

from openai import OpenAI


COST_PER_MINUTE = 0.006          # whisper-1: $0.006/min
MAX_BYTES       = 24 * 1024 * 1024  # 24 MB — stay under the 25 MB API limit


def transcribe_audio(
    audio_path: str | Path,
    language: Optional[str] = "en",
) -> dict:
    """
    Transcribe an audio file using OpenAI Whisper.
    Files over 24 MB are split into chunks and transcribed sequentially;
    timestamps are offset so the merged result is continuous.
    Returns full transcript, timing segments, and cost.
    """
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    if audio_path.stat().st_size <= MAX_BYTES:
        return _transcribe_single(client, audio_path, language)
    else:
        print(f"    File is {audio_path.stat().st_size / 1024 / 1024:.1f} MB — splitting into chunks...")
        return _transcribe_chunked(client, audio_path, language)


def _transcribe_single(client: OpenAI, audio_path: Path, language: Optional[str]) -> dict:
    """Transcribe a single file that fits within the API size limit."""
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language=language,
            response_format="verbose_json",
        )
    return _build_result(response.text, response.segments or [], response.duration, response.language or language)


def _transcribe_chunked(client: OpenAI, audio_path: Path, language: Optional[str]) -> dict:
    """
    Split the audio file into MAX_BYTES chunks and transcribe each one.
    Whisper robustly handles chunks that start mid-frame; timing is adjusted
    using each chunk's reported duration so the merged segments are continuous.
    """
    data = audio_path.read_bytes()
    suffix = audio_path.suffix  # preserve .mp3 / .m4a / etc. so Whisper decodes correctly

    # Build chunk byte ranges
    chunks = []
    offset = 0
    while offset < len(data):
        end = min(offset + MAX_BYTES, len(data))
        chunks.append(data[offset:end])
        offset = end

    all_segments = []
    full_text_parts = []
    time_offset = 0.0
    total_duration = 0.0
    detected_language = language

    for i, chunk_bytes in enumerate(chunks, 1):
        print(f"    Chunk {i}/{len(chunks)} ({len(chunk_bytes) / 1024 / 1024:.1f} MB)...")
        # Write chunk to a named temp file so OpenAI SDK gets the right filename/extension
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(chunk_bytes)
            tmp_path = Path(tmp.name)

        try:
            with open(tmp_path, "rb") as f:
                response = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language=language,
                    response_format="verbose_json",
                )
        finally:
            tmp_path.unlink(missing_ok=True)

        chunk_duration = float(response.duration or 0)
        for seg in (response.segments or []):
            all_segments.append({
                "start": seg.start + time_offset,
                "end":   seg.end   + time_offset,
                "text":  seg.text.strip(),
            })

        full_text_parts.append(response.text.strip())
        time_offset     += chunk_duration
        total_duration  += chunk_duration
        detected_language = response.language or detected_language

    full_text = " ".join(full_text_parts)
    return _build_result(full_text, all_segments, total_duration, detected_language or language)


def _build_result(
    text: str,
    segments: list,
    duration: float,
    language: str,
) -> dict:
    # Normalise segments — accept both dicts (chunked path) and Whisper objects (single path)
    seg_dicts = []
    for seg in segments:
        if isinstance(seg, dict):
            seg_dicts.append(seg)
        else:
            seg_dicts.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})

    timestamps_raw = "\n".join(
        f"[{_fmt_time(s['start'])}] {s['text']}" for s in seg_dicts
    )
    duration = float(duration or 0)
    cost_usd = round((duration / 60) * COST_PER_MINUTE, 4)

    return {
        "transcript":       text,
        "segments":         seg_dicts,
        "timestamps_raw":   timestamps_raw,
        "duration_seconds": duration,
        "cost_usd":         cost_usd,
        "language":         language,
    }


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"
