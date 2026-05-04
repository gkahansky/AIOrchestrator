"""Shared types for lead source handlers."""
from dataclasses import dataclass, field


@dataclass
class RawPost:
    title: str = ""
    text: str = ""          # the actual post/query body — preserved as lead.context
    author: str = ""
    url: str = ""
    email: str = ""         # pre-extracted email (Listen Notes, Fiverr buyer requests)
    website_url: str = ""   # pre-extracted website
    source_channel: str = ""
