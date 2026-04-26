"""
Platform skill: generate_newsletter_draft

Generates a full email newsletter edition from a transcript + episode context.
Produces subject lines (A/B), preview text, and the complete body.
Venture-agnostic — never references any specific venture.
"""

import os

import anthropic


_SYSTEM_PROMPT = """\
You are an expert email copywriter who transforms audio and video content into \
engaging newsletter editions that drive replies, shares, and listens. \
Your newsletters are conversational but authoritative. \
Follow output structure instructions exactly — no extra commentary.\
"""


def generate_newsletter_draft(
    transcript: str,
    context: dict,
    word_count_range: tuple[int, int] = (300, 500),
    brand_voice_injection: str = "",
    anthropic_api_key: str | None = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 2048,
) -> dict:
    """
    Generate a full newsletter edition from a transcript.

    Args:
        transcript:            Full episode/video transcript.
        context: {
            title:             Episode or video title.
            host_name:         Host name.
            guest_name:        Guest name (optional).
            niche:             Content niche.
            audience:          Target audience description.
            show_name:         Podcast/channel name.
            show_notes:        Episode summary (optional — used instead of full transcript).
        }
        word_count_range:      Target (min, max) word count for the body.
        brand_voice_injection: Brand voice context to prepend (optional).
        anthropic_api_key:     Falls back to ANTHROPIC_API_KEY env var.
        model:                 Claude model.
        max_tokens:            Max output tokens.

    Returns:
        {
            "subject_a":       str,   # Primary subject line
            "subject_b":       str,   # A/B test variant
            "preview_text":    str,   # 85–90 char preview text
            "body_text":       str,   # Full newsletter body (plain text)
            "body_html":       str,   # Full newsletter body (HTML)
            "word_count":      int,
            "cost_usd":        float,
        }
    """
    api_key = anthropic_api_key or os.environ["ANTHROPIC_API_KEY"]
    client = anthropic.Anthropic(api_key=api_key)

    min_words, max_words = word_count_range

    brand_block = ""
    if brand_voice_injection:
        brand_block = f"\nBRAND VOICE (apply throughout):\n{brand_voice_injection}\n"

    show_notes = context.get("show_notes", "")
    content_block = (
        f"EPISODE SUMMARY:\n{show_notes[:1500]}\n\nTRANSCRIPT EXCERPT:\n{transcript[:3000]}"
        if show_notes
        else f"TRANSCRIPT:\n{transcript[:5000]}"
    )

    guest_line = f"GUEST: {context.get('guest_name')}\n" if context.get("guest_name") else ""

    prompt = f"""\
Write a full email newsletter edition based on the content below.

TITLE: {context.get("title", "Episode")}
SHOW: {context.get("show_name", "")}
HOST: {context.get("host_name", "")}
{guest_line}NICHE: {context.get("niche", "general")}
AUDIENCE: {context.get("audience", "general audience")}
TARGET BODY LENGTH: {min_words}–{max_words} words
{brand_block}
{content_block}

---
Output using these exact markers:

===SUBJECT_A===
(Primary subject line — curiosity-driven or value-led, max 50 chars)

===SUBJECT_B===
(A/B variant — different angle: question, number, or bold claim, max 50 chars)

===PREVIEW_TEXT===
(Email preview text — 85–90 chars, continues the subject line's hook naturally)

===BODY===
(Full newsletter body in plain text. Structure:
  1. Opening hook paragraph — 2–3 sentences that expand on the subject line
  2. Three key takeaways from the episode, introduced with "Here's what stood out:"
     Format each as: "→ [Takeaway headline]: [1-2 sentence explanation]"
  3. One pull quote from the episode (format: "\"Quote text\" — Speaker Name")
  4. Closing paragraph with CTA: listen / share / reply

Stay within {min_words}–{max_words} words total. Write conversationally — \
as if writing to a friend who trusts your taste.)

===BODY_HTML===
(Same content as BODY but wrapped in semantic HTML: p, strong, blockquote tags. \
No h1/h2. Use <p> for paragraphs, <blockquote> for the pull quote, \
<strong> for the → takeaway headlines.)
"""

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    parsed = _parse_response(raw)

    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )
    parsed["cost_usd"] = cost_usd
    parsed["word_count"] = len(parsed.get("body_text", "").split())
    return parsed


def _parse_response(text: str) -> dict:
    markers = {
        "===SUBJECT_A===":    "subject_a",
        "===SUBJECT_B===":    "subject_b",
        "===PREVIEW_TEXT===": "preview_text",
        "===BODY===":         "body_text",
        "===BODY_HTML===":    "body_html",
    }
    result: dict = {v: "" for v in markers.values()}
    current_key: str | None = None
    buffer: list[str] = []

    def flush():
        if current_key:
            result[current_key] = "\n".join(buffer).strip()

    for line in text.split("\n"):
        stripped = line.strip()
        matched = None
        for marker, key in markers.items():
            if stripped == marker:
                matched = key
                break
        if matched:
            flush()
            buffer = []
            current_key = matched
        else:
            if current_key:
                buffer.append(line)

    flush()
    return result
