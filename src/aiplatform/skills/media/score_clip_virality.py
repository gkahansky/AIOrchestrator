"""
Platform skill: score_clip_virality

Uses Claude to identify and score the most viral-worthy 30–90 second windows
in a transcript with timing segments. Venture-agnostic.
"""

import json
import os
import re

import anthropic

_SYSTEM = """\
You are an expert short-form video strategist who identifies the most engaging,
shareable moments in long-form audio/video content. You analyse transcripts with
timestamps and score candidate clip windows for virality potential across social
media platforms (TikTok, Instagram Reels, YouTube Shorts, LinkedIn).

Viral signals to look for:
- Strong hooks or opening statements
- Emotional peaks (surprise, humour, insight, vulnerability)
- Quotable, self-contained insights or opinions
- Counterintuitive claims or myth-busting moments
- Story climaxes or punchy endings
- High-energy topic transitions

Score each window 0.0–1.0. Be selective — only windows with genuine viral
potential should score above 0.6. Return ONLY valid JSON, no commentary.
"""

_CLIP_MIN_S = 30
_CLIP_MAX_S = 90


def score_clip_virality(
    transcript: str,
    segments: list[dict],
    duration_s: float,
    max_clips: int = 5,
    anthropic_api_key: str | None = None,
    model: str = "claude-sonnet-4-6",
) -> dict:
    """
    Score viral clip windows from a timed transcript.

    Args:
        transcript:   Full transcript text.
        segments:     Whisper segments: [{start, end, text}, ...]
        duration_s:   Total video duration in seconds.
        max_clips:    Maximum number of clips to score (caller enforces plan limit).
        anthropic_api_key: Optional override; falls back to ANTHROPIC_API_KEY env var.
        model:        Claude model to use.

    Returns:
        {
            "clips": [
                {
                    "start_s": float,
                    "end_s": float,
                    "score": float,       # 0.0–1.0
                    "hook": str,          # one-sentence hook description
                    "reason": str,        # why this clips is viral
                    "transcript_chunk": str,
                }
            ],
            "cost_usd": float,
        }
    """
    client = anthropic.Anthropic(api_key=anthropic_api_key or os.environ["ANTHROPIC_API_KEY"])

    # Build a condensed timeline string for Claude
    timeline_lines = []
    for seg in segments:
        start = int(seg["start"])
        m, s = divmod(start, 60)
        timeline_lines.append(f"[{m:02d}:{s:02d}] {seg['text'].strip()}")
    timeline_str = "\n".join(timeline_lines)

    prompt = f"""\
Analyse this transcript and identify the {max_clips} best candidate windows for short-form video clips.

CONSTRAINTS:
- Each clip must be {_CLIP_MIN_S}–{_CLIP_MAX_S} seconds long
- Clips must not overlap by more than 10 seconds
- Total video duration: {int(duration_s)}s
- Select exactly {max_clips} clips (fewer only if the content doesn't have {max_clips} viable moments)

TIMED TRANSCRIPT:
{timeline_str}

Return a JSON array of clip objects. Each object must have:
- "start_s": number (clip start in seconds)
- "end_s": number (clip end in seconds, must be start_s + 30–90)
- "score": number 0.0–1.0
- "hook": string (one-sentence hook for this clip)
- "reason": string (why this clip is viral-worthy)
- "transcript_chunk": string (the relevant transcript text for this window)

Example format:
[{{"start_s": 142, "end_s": 207, "score": 0.87, "hook": "...", "reason": "...", "transcript_chunk": "..."}}]

Return ONLY the JSON array, nothing else."""

    response = client.messages.create(
        model=model,
        max_tokens=8192,   # 15 clips × ~300 tokens each ≈ 4500; headroom for long transcript_chunks
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_usd = round(input_tokens * 3e-6 + output_tokens * 15e-6, 4)

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        clips = json.loads(raw)
    except json.JSONDecodeError:
        # Response was truncated — drop the last incomplete object and close the array
        trimmed = re.sub(r",\s*\{[^{]*$", "", raw).rstrip(",").rstrip()
        if not trimmed.endswith("]"):
            trimmed += "]"
        try:
            clips = json.loads(trimmed)
        except json.JSONDecodeError as exc2:
            raise RuntimeError(
                f"Virality scorer returned unparseable JSON: {exc2}. "
                f"First 300 chars: {raw[:300]}"
            )

    # Clamp durations to valid range
    valid = []
    for c in clips:
        start = max(0.0, float(c["start_s"]))
        end = min(float(duration_s), float(c["end_s"]))
        dur = end - start
        if dur < _CLIP_MIN_S:
            end = min(float(duration_s), start + _CLIP_MIN_S)
        if dur > _CLIP_MAX_S:
            end = start + _CLIP_MAX_S
        c["start_s"] = start
        c["end_s"] = end
        c["score"] = float(c.get("score", 0.5))
        valid.append(c)

    return {"clips": valid, "cost_usd": cost_usd}
