"""
Lead source handlers — one module per platform.

Each handler exposes a single function:
    search(keywords: list[str], config: dict) -> list[RawPost]

Import the registry to resolve a platform name to its handler:
    from aiplatform.skills.research.sources import HANDLERS
    posts = HANDLERS["reddit"].search(keywords, config)
"""
from aiplatform.skills.research.sources import (
    reddit, google, linkedin, facebook,
    hackernews, indiehackers, fiverr, listennotes,
    youtube, instagram,
)

HANDLERS = {
    "reddit":       reddit,
    "google":       google,
    "linkedin":     linkedin,
    "facebook":     facebook,
    "hackernews":   hackernews,
    "indiehackers": indiehackers,
    "fiverr":       fiverr,
    "listennotes":  listennotes,
    "youtube":      youtube,
    "instagram":    instagram,
}

VALID_PLATFORMS = set(HANDLERS.keys())
