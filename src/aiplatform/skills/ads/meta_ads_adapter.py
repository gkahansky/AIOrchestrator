"""
Meta Ads adapter for the AdProvider interface.

Required env vars:
  META_ACCESS_TOKEN   — System User Access Token (long-lived, never expires)
  META_AD_ACCOUNT_ID  — Ad account ID, prefixed with 'act_' (e.g. act_123456789)
  META_APP_ID         — App ID from Meta for Developers
  META_APP_SECRET     — App secret from Meta for Developers

Meta for Developers setup:
  1. Create app at developers.facebook.com
  2. Add Marketing API product
  3. Request ads_read + ads_management permissions
  4. Create a System User under Business Settings and generate a long-lived token
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal

from aiplatform.skills.ads.ad_provider import AdProvider, CampaignStats, CreativeFormat

log = logging.getLogger(__name__)

_SUPPORTED_FORMATS = [
    CreativeFormat("Square",          1080, 1080, "1:1",  "image"),
    CreativeFormat("Story / Reels",   1080, 1920, "9:16", "image"),
    CreativeFormat("Portrait",        1080, 1350, "4:5",  "image"),
    CreativeFormat("Landscape",       1200,  628, "1.91:1", "image"),
    CreativeFormat("Carousel Tile",   1080, 1080, "1:1",  "image"),
]


class MetaAdsAdapter(AdProvider):

    @property
    def vendor_name(self) -> str:
        return "meta"

    def is_configured(self) -> bool:
        required = [
            "META_ACCESS_TOKEN",
            "META_AD_ACCOUNT_ID",
            "META_APP_ID",
            "META_APP_SECRET",
        ]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            log.debug("MetaAdsAdapter: missing env vars %s", missing)
            return False
        return True

    def _api(self):
        """Return a facebook_business FacebookAdsApi instance."""
        try:
            from facebook_business.api import FacebookAdsApi  # type: ignore
            from facebook_business.adobjects.adaccount import AdAccount  # type: ignore
        except ImportError:
            raise RuntimeError(
                "facebook-business package not installed. Run: pip install facebook-business"
            )
        FacebookAdsApi.init(
            app_id=os.environ["META_APP_ID"],
            app_secret=os.environ["META_APP_SECRET"],
            access_token=os.environ["META_ACCESS_TOKEN"],
        )
        return AdAccount(os.environ["META_AD_ACCOUNT_ID"])

    def create_campaign(
        self,
        name: str,
        daily_budget_usd: float,
        total_budget_usd: float | None = None,
    ) -> str:
        try:
            from facebook_business.adobjects.campaign import Campaign as FBCampaign  # type: ignore
        except ImportError:
            raise RuntimeError("facebook-business package not installed.")

        account = self._api()
        params = {
            FBCampaign.Field.name: name,
            FBCampaign.Field.objective: "OUTCOME_TRAFFIC",
            FBCampaign.Field.status: "PAUSED",  # start paused until approved
            FBCampaign.Field.daily_budget: int(daily_budget_usd * 100),  # cents
            FBCampaign.Field.special_ad_categories: [],
        }
        if total_budget_usd:
            params[FBCampaign.Field.lifetime_budget] = int(total_budget_usd * 100)

        campaign = account.create_campaign(params=params)
        external_id = campaign["id"]
        log.info("Meta campaign created: %s (id=%s)", name, external_id)
        return str(external_id)

    def get_stats(self, external_id: str) -> CampaignStats:
        try:
            from facebook_business.adobjects.campaign import Campaign as FBCampaign  # type: ignore
        except ImportError:
            raise RuntimeError("facebook-business package not installed.")

        self._api()  # initialise auth
        campaign = FBCampaign(fbid=external_id)
        insights = campaign.get_insights(fields=["spend", "clicks", "impressions"])

        if not insights:
            return CampaignStats(
                campaign_id=external_id, spend=Decimal(0), clicks=0, impressions=0
            )
        row = insights[0]
        spend = Decimal(str(row.get("spend", "0")))
        clicks = int(row.get("clicks", 0))
        impressions = int(row.get("impressions", 0))
        cpa = (spend / clicks) if clicks else None
        return CampaignStats(
            campaign_id=external_id,
            spend=spend,
            clicks=clicks,
            impressions=impressions,
            cpa=cpa,
        )

    def toggle_status(self, external_id: str, active: bool) -> None:
        try:
            from facebook_business.adobjects.campaign import Campaign as FBCampaign  # type: ignore
        except ImportError:
            raise RuntimeError("facebook-business package not installed.")

        self._api()
        campaign = FBCampaign(fbid=external_id)
        campaign.api_update(
            fields=[],
            params={"status": "ACTIVE" if active else "PAUSED"},
        )
        log.info(
            "Meta campaign %s → %s", external_id, "ACTIVE" if active else "PAUSED"
        )

    def get_supported_formats(self) -> list[CreativeFormat]:
        return _SUPPORTED_FORMATS


def get_adapter(vendor: str) -> AdProvider:
    """Factory: return the correct adapter for a vendor slug."""
    from aiplatform.skills.ads.google_ads_adapter import GoogleAdsAdapter
    adapters: dict[str, AdProvider] = {
        "google": GoogleAdsAdapter(),
        "meta":   MetaAdsAdapter(),
    }
    if vendor not in adapters:
        raise ValueError(f"Unknown ad vendor '{vendor}'. Supported: {list(adapters)}")
    return adapters[vendor]


def available_vendors() -> list[str]:
    """Return vendor slugs whose credentials are fully configured."""
    from aiplatform.skills.ads.google_ads_adapter import GoogleAdsAdapter
    candidates = [GoogleAdsAdapter(), MetaAdsAdapter()]
    return [a.vendor_name for a in candidates if a.is_configured()]
