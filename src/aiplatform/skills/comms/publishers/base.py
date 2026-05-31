"""
Publisher contract — shared types for the social-publishing registry.

Each platform handler exposes a single function:
    publish(req: PublishRequest, config: dict) -> PublishResult

Handlers are venture-agnostic and stateless: they receive everything they
need on the PublishRequest and return a PublishResult. They never touch the
database — all persistence (publish_jobs, content_items.published_at,
content_assets.url) is the caller's job.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PublishRequest:
    """Everything a publisher needs to ship one piece of content."""
    body: str
    channel: str
    title: str = ""
    hashtags: list[str] = field(default_factory=list)
    media_paths: list[str] = field(default_factory=list)  # local files OR URLs
    media_urls: list[str] = field(default_factory=list)   # public URLs (some APIs prefer these)
    scheduled_for_iso: str = ""                           # let the platform schedule if supported
    meta: dict = field(default_factory=dict)              # caller-injected extras


@dataclass
class PublishResult:
    """Outcome of a publish attempt.

    status:
      success         — published; external_post_id/external_url are set
      awaiting_manual — staged for assisted send; operator must publish + confirm
      failed          — publish failed; caller leaves the item in `failed` for retry
    """
    status: str
    external_post_id: str = ""
    external_url: str = ""
    deep_link: str = ""         # URL the operator opens to publish manually (assisted)
    instructions: str = ""      # short operator guidance for assisted send
    error: str = ""
    provider: str = ""          # "linkedin_api" | "meta_graph" | "youtube_data" | "manual"
    response: dict = field(default_factory=dict)
