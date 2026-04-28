"""
Platform skill: generate_show_notes

Generates structured podcast/video show notes from a transcript.
Produces key takeaways, chapter timestamps, and a concise episode summary.
Venture-agnostic.
"""

import os
import re

import anthropic


_SYSTEM = """\
You are an expert podcast producer who writes clear, structured show notes.
Show notes help listeners navigate episodes and entice new listeners to tune in.
Follow the output format exactly — no extra commentary outside the requested sections.
"""


def generate_show_notes(
    transcript: str,
    context: dict,
    segments: list[dict] | None = None,
    brand_voice_injection: str = "",
    anthropic_api_key: str | None = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 3072,
) -> dict:
    """
    Generate structured show notes from a transcript.

    Args:
        transcript:            Full transcript text.
        context:               Dict with: show_name, episode_title, host_name, guest_name (optional).
        segments:              Whisper segments for timestamp generation (optional).
        brand_voice_injection: Optional brand voice guide.
        anthropic_api_key:     Optional override.
        model:                 Claude model.
        max_tokens:            Max output tokens.

    Returns:
        {
            "summary": str,           # 2-3 sentence episode summary
            "key_takeaways": list,    # 5 bullet points
            "timestamps": str,        # formatted chapter markers
            "guest_bio": str,         # if guest info present, else ""
            "full_show_notes": str,   # complete formatted show notes
            "cost_usd": float,
        }
    """
    client = anthropic.Anthropic(api_key=anthropic_api_key or os.environ["ANTHROPIC_API_KEY"])

    show_name = context.get("show_name", "the show")
    episode_title = context.get("episode_title", "this episode")
    host_name = context.get("host_name", "the host")
    guest_name = context.get("guest_name", "")

    timestamps_block = ""
    if segments:
        lines = []
        for seg in segments[::max(1, len(segments) // 12)]:  # ~12 chapter markers
            m, s = divmod(int(seg["start"]), 60)
            lines.append(f"[{m:02d}:{s:02d}] {seg['text'].strip()[:80]}")
        timestamps_block = "\n\nRAW TIMESTAMPS (for chapter generation):\n" + "\n".join(lines)

    voice_block = f"\n\nBRAND VOICE:\n{brand_voice_injection}" if brand_voice_injection else ""
    guest_block = f"\nGuest: {guest_name}" if guest_name else ""

    prompt = f"""\
Write complete show notes for this podcast episode.

Show: {show_name}
Episode: {episode_title}
Host: {host_name}{guest_block}{voice_block}{timestamps_block}

TRANSCRIPT (truncated to 6000 chars):
{transcript[:6000]}

Produce exactly these sections:

===SUMMARY===
2–3 sentence episode overview that entices new listeners.

===KEY_TAKEAWAYS===
- Takeaway 1
- Takeaway 2
- Takeaway 3
- Takeaway 4
- Takeaway 5

===TIMESTAMPS===
[MM:SS] Chapter title
[MM:SS] Chapter title
(list 6–12 chapters)

===GUEST_BIO===
(2–3 sentences about the guest if applicable; leave blank if no guest)

===FULL_SHOW_NOTES===
Complete, formatted show notes combining all sections in a reader-friendly layout."""

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_usd = round(input_tokens * 3e-6 + output_tokens * 15e-6, 4)

    def _extract(tag: str) -> str:
        m = re.search(rf"==={tag}===\s*(.*?)(?====\w+===|\Z)", raw, re.DOTALL)
        return m.group(1).strip() if m else ""

    summary = _extract("SUMMARY")
    takeaways_raw = _extract("KEY_TAKEAWAYS")
    takeaways = [t.lstrip("- •").strip() for t in takeaways_raw.splitlines() if t.strip()]
    timestamps = _extract("TIMESTAMPS")
    guest_bio = _extract("GUEST_BIO")
    full_notes = _extract("FULL_SHOW_NOTES") or raw

    return {
        "summary": summary,
        "key_takeaways": takeaways,
        "timestamps": timestamps,
        "guest_bio": guest_bio,
        "full_show_notes": full_notes,
        "cost_usd": cost_usd,
    }
