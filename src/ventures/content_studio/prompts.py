"""
Content Studio prompts — tier-aware podcast content generation.

Uses a single Claude API call per order to generate all required sections at once.
Sections are delimited by ===SECTION: NAME=== markers for deterministic parsing.
"""

from ventures.content_studio.config import TIERS


SYSTEM_PROMPT = """\
You are an expert podcast content writer producing professional show notes \
and marketing materials. Your writing is engaging, SEO-aware, and precisely \
formatted. You follow output structure instructions exactly — no deviations, \
no missing sections, no extra commentary outside the requested sections.\
"""

# Section delimiter used for parsing
_SEP = "===SECTION:"


def build_content_prompt(order: dict, transcript_data: dict) -> str:
    """
    Build the user message for Claude based on order tier.

    Args:
        order:           The order dict with show_name, episode_title, host_name,
                         niche, audience, tier fields.
        transcript_data: Output from transcribe_audio skill — contains transcript
                         and timestamps_raw.
    """
    tier = order["tier"]
    sections = TIERS[tier]["sections"]

    header = f"""\
Create a podcast content package for the episode below.

SHOW: {order.get("show_name", "Unknown Show")}
EPISODE: {order.get("episode_title", "Unknown Episode")}
HOST: {order.get("host_name", "Unknown Host")}
NICHE: {order.get("niche", "general")}
AUDIENCE: {order.get("audience", "general audience")}
TIER: {tier.upper()} — generate only the sections listed below.

WHISPER TIMING REFERENCE (one segment per line — use these start times for timestamps):
{transcript_data.get("timestamps_raw", "[no timing data]")}

FULL TRANSCRIPT:
{transcript_data.get("transcript", "[no transcript]")}

---
Generate the following sections in order. Start each section with its exact marker \
on its own line: {_SEP} SECTION_NAME===
"""

    section_instructions = {
        "show_notes": f"""\
{_SEP} SHOW_NOTES===
Write a 300–500 word engaging show notes summary. Include:
- 2–3 sentence episode overview
- Key topics covered (bullet list)
- 3–5 main listener takeaways (bullet list)
- One clear call to action for listeners
""",
        "timestamps": f"""\
{_SEP} TIMESTAMPS===
Generate 8–12 chapter markers using the Whisper timing reference above.
Format each line exactly as: MM:SS – Topic Name
Group segments into meaningful topics — do not list every sentence.
""",
        "guest_bio": f"""\
{_SEP} GUEST_BIO===
If the episode features a guest, write a 2–3 paragraph professional bio based on \
what is mentioned in the transcript (credentials, background, expertise, any links/handles mentioned).
If no guest appears, write a 1-paragraph host spotlight for this episode.
""",
        "transcript": f"""\
{_SEP} TRANSCRIPT===
Output a clean, lightly-formatted version of the full transcript.
Use "HOST:" and "GUEST:" speaker labels. Fix obvious transcription errors. \
Preserve all content — do not summarise or truncate.
""",
        "social_captions": f"""\
{_SEP} SOCIAL_CAPTIONS===
Generate 5 platform-specific captions — label each clearly:

INSTAGRAM 1: Hook-driven post (hook line + 3–5 sentences + CTA + 10 hashtags)
INSTAGRAM 2: Alternative angle or quote-based post (different hook from #1)
LINKEDIN: Professional framing (3–4 sentences, no more than 5 hashtags, insight-led)
TWITTER/X: Punchy, max 280 chars, ends with [LINK]
FACEBOOK: Conversational tone, 2–3 sentences, 2–3 hashtags
""",
        "newsletter_excerpt": f"""\
{_SEP} NEWSLETTER_EXCERPT===
Write a 150–200 word email newsletter teaser. Include:
- Compelling opening hook
- 2–3 key insights (tease, don't fully reveal)
- Clear CTA: "Listen to the full episode → [LINK]"
""",
        "seo_metadata": f"""\
{_SEP} SEO_METADATA===
Provide the following on separate labelled lines:
TITLE: Search-optimised episode title (max 60 chars)
META_DESCRIPTION: Meta description with primary keyword (max 155 chars)
KEYWORDS: 12–15 comma-separated keyword tags relevant to the episode
""",
    }

    body = header
    for section in sections:
        body += "\n" + section_instructions[section]

    return body


def parse_content_response(text: str, tier: str) -> dict:
    """
    Parse the Claude response into a content sections dict.
    Sections are split by ===SECTION: NAME=== markers.

    Returns a dict with keys matching the tier's section list.
    Missing sections get an empty string — never raises.
    """
    sections = TIERS[tier]["sections"]
    result = {s: "" for s in sections}

    # Map marker names back to section keys
    marker_map = {
        "SHOW_NOTES": "show_notes",
        "TIMESTAMPS": "timestamps",
        "GUEST_BIO": "guest_bio",
        "TRANSCRIPT": "transcript",
        "SOCIAL_CAPTIONS": "social_captions",
        "NEWSLETTER_EXCERPT": "newsletter_excerpt",
        "SEO_METADATA": "seo_metadata",
    }

    lines = text.split("\n")
    current_key = None
    buffer: list[str] = []

    def _flush():
        if current_key and current_key in result:
            result[current_key] = "\n".join(buffer).strip()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(_SEP) and stripped.endswith("==="):
            _flush()
            buffer = []
            marker_name = stripped[len(_SEP):].rstrip("=").strip()
            current_key = marker_map.get(marker_name)
        else:
            if current_key:
                buffer.append(line)

    _flush()
    return result
