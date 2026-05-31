"""Content Engine config — brand registry, channel matrix, generation knobs.

Brand rows live in the database (`content_brands` table). This module holds
**seed defaults** the API uses when bootstrapping a new brand, plus venture-
wide constants that don't belong in the DB.

Adding a new brand is a `POST /api/ventures/content-engine/brands` with its
own `theme_weights` / `voice_profile_json` / `banned_phrases`. The seed below
is what the EchoForge Accessibility row will be created from on first launch.
"""
from __future__ import annotations

# ── Channels ──────────────────────────────────────────────────────────────────

VALID_CHANNELS = (
    "linkedin_page",
    "facebook_page",
    "instagram_business",
    "youtube_channel",
)

VALID_FORMATS = (
    "post",         # single-image or text post
    "carousel",     # multi-image (LinkedIn / IG)
    "reel",         # short vertical video (IG / FB reel)
    "short",        # YouTube Short
    "long_video",   # YouTube long-form
    "blog",         # off-platform blog (article)
    "newsletter",   # email newsletter
)

# Which channels accept which formats (used by the strategy generator).
CHANNEL_FORMATS: dict[str, tuple[str, ...]] = {
    "linkedin_page":      ("post", "carousel", "long_video"),
    "facebook_page":      ("post", "carousel", "reel"),
    "instagram_business": ("post", "carousel", "reel"),
    "youtube_channel":    ("short", "long_video"),
}

# Default posts-per-week per channel for a freshly created brand. The brand
# row keeps its own override in `channel_cadence` — this is the seed only.
DEFAULT_CHANNEL_CADENCE: dict[str, int] = {
    "linkedin_page":      3,
    "facebook_page":      2,
    "instagram_business": 3,
    "youtube_channel":    1,
}


# ── EchoForge Accessibility seed ──────────────────────────────────────────────

ECHOFORGE_ACCESSIBILITY_SEED = {
    "slug": "echoforge_accessibility",
    "name": "EchoForge Accessibility",
    "venture_tag": "accessibility_audit",
    "description": (
        "Web accessibility audits & remediation guidance. Owned by EchoForge "
        "(echoforge.biz). Content educates SMB owners and engineering leads on "
        "ADA / EAA / WCAG 2.2 compliance and the business case for accessible "
        "products."
    ),
    "theme_weights": {"accessibility": 0.7, "adjacent": 0.3},
    "channel_cadence": dict(DEFAULT_CHANNEL_CADENCE),
    "target_personas": [
        {
            "name": "SMB Owner — risk-aware",
            "description": (
                "Owns or runs a small-to-mid online business. Heard about the "
                "European Accessibility Act / ADA lawsuits and worries the "
                "site is exposed. Time-poor, no in-house engineer. Wants a "
                "plain-English picture of the risk and a fix path."
            ),
        },
        {
            "name": "Engineering Lead — quality-driven",
            "description": (
                "Frontend lead or staff engineer at a 20–200 person product "
                "company. Already values quality but accessibility is the "
                "discipline they know least. Wants concrete WCAG patterns, "
                "automation tooling, and a way to justify the investment."
            ),
        },
        {
            "name": "Product Manager — compliance & UX",
            "description": (
                "Owns a SaaS product. Compliance is on the roadmap because a "
                "buyer in the pipeline asked for a VPAT. Needs to understand "
                "scope, cost, and ongoing process — not deep WCAG references."
            ),
        },
    ],
    # Phrases the AI-tell critic auto-rejects. Lowercased substring match.
    "banned_phrases": [
        "in today's fast-paced world",
        "let's dive into",
        "in conclusion",
        "harness the power",
        "unlock the potential",
        "leverage cutting-edge",
        "embrace the future",
        "navigate the complexities",
        "at the end of the day",
        "it's not just about",  # the "it's not just X, it's Y" cliché
        "needle-mover",
        "game-changer",
        "synergy",
    ],
    # Brand voice — seed shape. Will be replaced with a generated profile via
    # generate_brand_voice once real source material is curated. The shape
    # mirrors what content_studio/pipeline.py:_load_brand_voice returns.
    "voice_profile_json": {
        "tone": [
            "Plain, direct, no jargon unless it's WCAG or legal terminology.",
            "Empathetic — accessibility failures hurt real users; never moralise.",
            "Confident without being preachy.",
        ],
        "vocabulary": [
            "Use 'people who use screen readers' over 'visually impaired users'.",
            "Say 'meets WCAG 2.2 AA' rather than 'compliant'.",
            "Avoid 'inclusive' as a stand-in for 'accessible' — they aren't synonyms.",
        ],
        "sentence_style": [
            "Mix short declarative sentences with one longer follow-up.",
            "Lead with the example, then the rule. Not the other way round.",
        ],
        "rhetorical_moves": [
            "Open with a real failure (a button that screen readers skip), then explain why.",
            "End with the smallest action the reader could take today.",
        ],
        "content_principles": [
            "Accessibility is a quality discipline, not a charity.",
            "If we can't prove it with a code snippet or a screen-reader transcript, we don't say it.",
            "Lawsuits are a real consequence but a poor lead — start with the user.",
        ],
        "topics_to_avoid": [
            "Hot-take politics.",
            "Vendor-bashing.",
            "AI doom or AI hype that isn't tied to a concrete accessibility implication.",
        ],
    },
    "auto_strategy_enabled": False,
}


# ── Quality knobs ─────────────────────────────────────────────────────────────

# AI-tell critic score threshold. Items below this need human edit before
# auto-approval can be enabled. (Manual approval always allowed.)
AI_TELL_MIN_SCORE = 80

# Calendar generation defaults.
DEFAULT_STRATEGY_PERIOD_DAYS = 30
DEFAULT_PILLARS = (
    "WCAG how-to (a single criterion explained)",
    "Real failure deep-dive (an audit finding, anonymised)",
    "Regulatory update (ADA / EAA / Section 508 news)",
    "Mythbuster (a common accessibility misconception)",
    "Adjacent quality / UX / SEO crossover",
)

# Per-channel content length budgets (used by the brief generator).
CHANNEL_LENGTH_BUDGETS: dict[str, dict] = {
    "linkedin_page":      {"min_chars":  600,  "max_chars": 2500,  "hashtags": (2, 5)},
    "facebook_page":      {"min_chars":  300,  "max_chars": 1200,  "hashtags": (0, 3)},
    "instagram_business": {"min_chars":  200,  "max_chars": 1500,  "hashtags": (5, 15)},
    "youtube_channel":    {"min_chars":  300,  "max_chars": 4500,  "hashtags": (3, 8)},
}

# Minimum cited sources per brief — drives specificity grounding.
MIN_SOURCES_PER_BRIEF = 2
