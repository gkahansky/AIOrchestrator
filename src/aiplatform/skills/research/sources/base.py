"""Shared types for lead source handlers."""
from dataclasses import dataclass, field


@dataclass
class RawPost:
    title: str = ""
    text: str = ""          # the actual post/query body — preserved as lead.context
    author: str = ""        # display name (fallback identity)
    url: str = ""           # the post/permalink where the signal was found
    email: str = ""         # pre-extracted email (Listen Notes, Fiverr buyer requests)
    website_url: str = ""   # pre-extracted website
    source_channel: str = ""
    # Author identity — the reachable profile of the person who posted. Captured
    # where the platform exposes it (linkedin/facebook/youtube/instagram) so the
    # operator can open a DM at send time.
    author_url: str = ""        # full profile/channel URL
    author_handle: str = ""     # platform handle / slug / id (no display name)
    # Relevance signals — used by the qualifier (recency/engagement/seniority) and
    # by source-side filters before the paid Claude step. Lossless when absent.
    posted_at: str = ""         # ISO 8601 timestamp of the post, if known
    engagement: int = 0         # reactions + comments (or platform equivalent)
    author_headline: str = ""   # role/title/occupation line, if exposed
