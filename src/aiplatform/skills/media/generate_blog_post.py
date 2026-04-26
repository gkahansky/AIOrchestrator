"""
Platform skill: generate_blog_post

Generates a full SEO blog post from a transcript + episode context.
Venture-agnostic — the caller supplies all content and context.
"""

import os

import anthropic


_SYSTEM_PROMPT = """\
You are an expert content writer who transforms audio/video transcripts into \
compelling, SEO-optimised blog posts. Your posts are engaging, well-structured, \
and written in a clear, authoritative voice. You follow output structure \
instructions exactly — no extra commentary outside the requested sections.\
"""


def generate_blog_post(
    transcript: str,
    context: dict,
    word_count_range: tuple[int, int] = (800, 1200),
    brand_voice_injection: str = "",
    anthropic_api_key: str | None = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
) -> dict:
    """
    Generate a full blog post from a transcript.

    Args:
        transcript:            The full episode/video transcript.
        context: {
            title:             Episode or video title.
            host_name:         Host name (used for attribution).
            guest_name:        Guest name, if any.
            niche:             Content niche (e.g. "business", "health").
            audience:          Target audience description.
            show_name:         Podcast/channel name.
            keywords:          List of seed SEO keywords (optional).
        }
        word_count_range:      Target (min, max) word count.
        brand_voice_injection: Prepended brand voice context (optional).
        anthropic_api_key:     API key (falls back to ANTHROPIC_API_KEY env var).
        model:                 Claude model to use.
        max_tokens:            Max output tokens.

    Returns:
        {
            "title":            str,  # H1 article title
            "meta_description": str,  # 155-char meta description
            "seo_tags":         list[str],  # 5 SEO keyword tags
            "body_html":        str,  # Full article as HTML
            "body_text":        str,  # Plain-text version
            "word_count":       int,
            "cost_usd":         float,
        }
    """
    api_key = anthropic_api_key or os.environ["ANTHROPIC_API_KEY"]
    client = anthropic.Anthropic(api_key=api_key)

    min_words, max_words = word_count_range
    keywords_line = ""
    kws = context.get("keywords")
    if kws:
        keywords_line = f"SEED KEYWORDS: {', '.join(kws)}\n"

    brand_block = ""
    if brand_voice_injection:
        brand_block = f"\nBRAND VOICE GUIDE (apply throughout):\n{brand_voice_injection}\n"

    prompt = f"""\
Write a full SEO blog post based on the transcript below.

TITLE/TOPIC: {context.get("title", "Episode")}
SHOW/CHANNEL: {context.get("show_name", "")}
HOST: {context.get("host_name", "")}
GUEST: {context.get("guest_name", "") or "N/A"}
NICHE: {context.get("niche", "general")}
AUDIENCE: {context.get("audience", "general audience")}
TARGET WORD COUNT: {min_words}–{max_words} words
{keywords_line}{brand_block}
TRANSCRIPT:
{transcript[:12000]}

---
Output the blog post using these exact markers:

===TITLE===
(H1 article title — engaging, includes primary keyword, max 70 chars)

===META_DESCRIPTION===
(155-char meta description — includes primary keyword, ends with a value statement)

===SEO_TAGS===
(5 comma-separated SEO keyword tags)

===BODY===
(Full article body. Structure:
  - Introduction paragraph (hook + episode overview, ~100 words)
  - 3–4 H2 sections with 2–3 paragraphs each
  - One pull quote (format: > "Quote text" — Speaker Name)
  - Conclusion with a clear CTA linking back to the episode)

Write the body in HTML (h2, p, blockquote tags only — no h1, no div, no script).
Stay within {min_words}–{max_words} words for the body section.
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
        "===TITLE===":            "title",
        "===META_DESCRIPTION===": "meta_description",
        "===SEO_TAGS===":         "seo_tags_raw",
        "===BODY===":             "body_html",
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

    # Post-process
    seo_raw = result.pop("seo_tags_raw", "")
    result["seo_tags"] = [t.strip() for t in seo_raw.split(",") if t.strip()]

    # Build plain-text body by stripping HTML tags
    import re
    body_html = result.get("body_html", "")
    result["body_text"] = re.sub(r"<[^>]+>", "", body_html).strip()

    return result
