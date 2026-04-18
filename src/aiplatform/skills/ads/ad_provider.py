"""
AdProvider — abstract interface for all ad platform adapters.

All adapters (Google, Meta, LinkedIn, X, …) must implement this interface.
The CampaignController routes through here — it never calls a platform SDK directly.

Never import from /ventures/ here. This skill is venture-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass
class CampaignStats:
    campaign_id: str
    spend: Decimal
    clicks: int
    impressions: int
    cpa: Decimal | None = None


@dataclass
class CreativeFormat:
    name: str           # e.g. "Square", "Story", "Banner"
    width: int
    height: int
    aspect_ratio: str   # e.g. "1:1", "9:16", "16:9"
    format_type: str    # e.g. "image", "video"


class AdProvider(ABC):
    """Abstract base for all ad platform adapters."""

    @property
    @abstractmethod
    def vendor_name(self) -> str:
        """Return the vendor slug: 'google' | 'meta' | etc."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if all required credentials are present in env."""

    @abstractmethod
    def create_campaign(
        self,
        name: str,
        daily_budget_usd: float,
        total_budget_usd: float | None = None,
    ) -> str:
        """
        Create a campaign on the vendor platform.
        Returns the vendor-assigned external campaign ID.
        """

    @abstractmethod
    def get_stats(self, external_id: str) -> CampaignStats:
        """Fetch current spend, clicks, and impressions from the vendor API."""

    @abstractmethod
    def toggle_status(self, external_id: str, active: bool) -> None:
        """Pause (active=False) or resume (active=True) a campaign."""

    @abstractmethod
    def get_supported_formats(self) -> list[CreativeFormat]:
        """Return the creative formats this vendor supports."""

    def stop_campaign(self, external_id: str) -> None:
        """Stop (permanently pause) a campaign. Defaults to toggle_status(False)."""
        self.toggle_status(external_id, active=False)
