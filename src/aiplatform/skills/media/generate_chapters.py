"""
Platform skill: generate_chapters

Segments a long-form video transcript into topical chapters using Claude.
Returns chapters with timestamps for the human chapter-review gate.
Venture-agnostic.
"""

import json

from anthropic import Anthropic


def generate_chapters(
    transcript: str,
    duration_s: float,
    anthropic_api_key: str,
    model: str = "claude-sonnet-4-6",
    max_chapters: int = 10,
) -> dict:
    """
    Generate topical chapter markers from a Whisper transcript.

    Args:
        transcript:        Full transcript text.
        duration_s:        Total video duration in seconds.
        anthropic_api_key: Anthropic API key.
        model:             Claude model to use.
        max_chapters:      Maximum number of chapters to generate (default 10).

    Returns:
        {
            "chapters": [
                {
                    "index":   int,
                    "title":   str,
                    "start_s": float,
                    "end_s":   float,
                    "summary": str,   # 1-2 sentences
                },
                ...
            ]
        }
    """
    client = Anthropic(api_key=anthropic_api_key)
    duration_min = max(1, int(duration_s / 60))
    min_chapters = min(5, max_chapters)

    prompt = (
        f"Analyse this {duration_min}-minute video transcript and identify "
        f"{min_chapters}–{max_chapters} distinct topical chapters.\n\n"
        "Rules:\n"
        "- Each chapter must cover a clear, self-contained topic or discussion segment\n"
        "- Chapters must be in chronological order with no gaps or overlaps\n"
        f"- start_s and end_s must be between 0 and {int(duration_s)}\n"
        "- The first chapter starts at 0; the last chapter ends at the video duration\n"
        "- summary: 1–2 sentences capturing the key insight or moment\n"
        "- Title: short, punchy, suitable as a YouTube chapter label\n\n"
        f"TRANSCRIPT (first 8000 chars):\n{transcript[:8000]}\n\n"
        "Respond with ONLY valid JSON — no markdown, no explanation:\n"
        '{"chapters": [{"index": 0, "title": "...", "start_s": 0.0, '
        f'"end_s": 120.0, "summary": "..."}}, ...]}}}'
    )

    response = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end <= start:
        return {"chapters": []}

    try:
        data = json.loads(raw[start:end])
    except json.JSONDecodeError:
        return {"chapters": []}

    chapters = data.get("chapters", [])
    for i, ch in enumerate(chapters):
        ch["index"]   = i
        ch["start_s"] = float(ch.get("start_s", 0))
        ch["end_s"]   = float(ch.get("end_s", duration_s))

    return {"chapters": chapters}
