"""
Platform skill: score_clip_virality

Uses Claude to identify and score the most viral-worthy clip windows in a
transcript with timing segments. Venture-agnostic.

Clip boundaries are snapped to the nearest Whisper segment boundary after
Claude responds, so clips never cut mid-sentence.  Length is context-driven
(30–120 s) rather than a fixed target.
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
_CLIP_MAX_S = 120


def score_clip_virality(
    transcript: str,
    segments: list[dict],
    duration_s: float,
    max_clips: int = 5,
    anthropic_api_key: str | None = None,
    model: str = "claude-sonnet-4-6",
    chapters: list[dict] | None = None,
) -> dict:
    """
    Score viral clip windows from a timed transcript.

    Args:
        transcript:        Full transcript text.
        segments:          Whisper segments: [{start, end, text}, ...]
        duration_s:        Total video duration in seconds.
        max_clips:         Maximum number of clips to score (caller enforces plan limit).
        anthropic_api_key: Optional override; falls back to ANTHROPIC_API_KEY env var.
        model:             Claude model to use.
        chapters:          Optional chapter list [{title, start_s, end_s, summary}, ...]
                           passed so Claude can respect natural topic boundaries.

    Returns:
        {
            "clips": [
                {
                    "start_s": float,
                    "end_s": float,
                    "score": float,
                    "hook": str,
                    "reason": str,
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

    # Optionally include chapter map so Claude can respect natural breaks
    chapter_block = ""
    if chapters:
        chapter_lines = []
        for ch in chapters:
            cs = int(ch.get("start_s", 0))
            ce = int(ch.get("end_s", 0))
            cm, cs2 = divmod(cs, 60)
            em, es2 = divmod(ce, 60)
            chapter_lines.append(
                f"  [{cm:02d}:{cs2:02d}–{em:02d}:{es2:02d}] {ch.get('title', '')} — {ch.get('summary', '')}"
            )
        chapter_block = "\nCHAPTER OUTLINE (respect these as natural topic boundaries):\n" + "\n".join(chapter_lines) + "\n"

    prompt = f"""\
Analyse this transcript and identify the {max_clips} best candidate windows for short-form video clips.

CONSTRAINTS:
- Each clip must be {_CLIP_MIN_S}–{_CLIP_MAX_S} seconds long
- Choose the length that fits the natural conversation — do NOT pad clips to fill a fixed duration
- A punchy standalone insight might be 35 s; a full story arc might be 110 s
- Clips must start and end at natural speech breaks (complete sentences, not mid-thought)
- Clips must not overlap by more than 10 seconds
- Total video duration: {int(duration_s)}s
- Select exactly {max_clips} clips (fewer only if the content does not have {max_clips} viable moments)
{chapter_block}
TIMED TRANSCRIPT:
{timeline_str}

Return a JSON array of clip objects. Each object must have:
- "start_s": number (clip start in seconds — must be at the start of a sentence)
- "end_s": number (clip end in seconds — must be at the end of a sentence, start_s + {_CLIP_MIN_S}–{_CLIP_MAX_S})
- "score": number 0.0–1.0
- "hook": string (one-sentence hook for this clip)
- "reason": string (why this clip is viral-worthy)
- "transcript_chunk": string (the relevant transcript text for this window)

Example format:
[{{"start_s": 142, "end_s": 207, "score": 0.87, "hook": "...", "reason": "...", "transcript_chunk": "..."}}]

Return ONLY the JSON array, nothing else."""

    response = client.messages.create(
        model=model,
        max_tokens=8192,
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
        last_close = raw.rfind("}")
        if last_close != -1:
            first_open = raw.find("[")
            if first_open != -1:
                truncated = raw[first_open : last_close + 1] + "]"
            else:
                truncated = "[" + raw[: last_close + 1] + "]"
            try:
                clips = json.loads(truncated)
            except json.JSONDecodeError as exc2:
                raise RuntimeError(
                    f"Virality scorer returned unparseable JSON: {exc2}. "
                    f"First 300 chars: {raw[:300]}"
                )
        else:
            raise RuntimeError(
                f"Virality scorer returned no parseable JSON. First 300 chars: {raw[:300]}"
            )

    # Build sorted list of all segment boundary timestamps for snapping
    boundaries = _build_boundaries(segments)

    valid = []
    for c in clips:
        start = max(0.0, float(c["start_s"]))
        end   = min(float(duration_s), float(c["end_s"]))

        # Snap to nearest Whisper segment boundary (±4 s tolerance)
        # so clips never cut mid-sentence
        start = _snap(start, boundaries, tolerance_s=4.0, prefer="start")
        end   = _snap(end,   boundaries, tolerance_s=4.0, prefer="end")

        # Enforce duration bounds after snapping
        dur = end - start
        if dur < _CLIP_MIN_S:
            end = min(float(duration_s), start + _CLIP_MIN_S)
        if dur > _CLIP_MAX_S:
            # Snap the new end back to a segment boundary too
            end = _snap(start + _CLIP_MAX_S, boundaries, tolerance_s=4.0, prefer="end")
            end = min(end, float(duration_s))

        c["start_s"] = round(start, 2)
        c["end_s"]   = round(end, 2)
        c["score"]   = float(c.get("score", 0.5))
        valid.append(c)

    return {"clips": valid, "cost_usd": cost_usd}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_boundaries(segments: list[dict]) -> list[float]:
    """Return a sorted list of all Whisper segment start + end timestamps."""
    seen: set[float] = set()
    for seg in segments:
        seen.add(float(seg.get("start", 0)))
        seen.add(float(seg.get("end", 0)))
    return sorted(seen)


def _snap(t: float, boundaries: list[float], tolerance_s: float, prefer: str) -> float:
    """
    Snap timestamp t to the nearest boundary within tolerance_s.

    prefer="start": among equidistant candidates, take the earlier one
                    (don't cut the opening word).
    prefer="end":   take the later one (don't cut the closing word).
    """
    if not boundaries:
        return t
    best = t
    best_dist = tolerance_s
    for b in boundaries:
        d = abs(b - t)
        if d < best_dist or (d == best_dist and prefer == "end" and b > best):
            best_dist = d
            best = b
    return best
