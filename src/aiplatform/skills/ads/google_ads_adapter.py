"""
Google Ads adapter for the AdProvider interface.

Required env vars:
  GOOGLE_ADS_DEVELOPER_TOKEN   — Google Ads API developer token
  GOOGLE_ADS_CLIENT_ID         — OAuth client ID (same app as Drive OAuth)
  GOOGLE_ADS_CLIENT_SECRET     — OAuth client secret
  GOOGLE_ADS_REFRESH_TOKEN     — OAuth refresh token with adwords scope
  GOOGLE_ADS_CUSTOMER_ID       — 10-digit Google Ads customer ID (no dashes)

OAuth scope required on GCP: https://www.googleapis.com/auth/adwords
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal

from aiplatform.skills.ads.ad_provider import AdProvider, CampaignStats, CreativeFormat

log = logging.getLogger(__name__)

_SUPPORTED_FORMATS = [
    CreativeFormat("Square",          1080, 1080, "1:1",  "image"),
    CreativeFormat("Landscape",       1200,  628, "16:9", "image"),
    CreativeFormat("Portrait",         960, 1200, "4:5",  "image"),
    CreativeFormat("Responsive",      1200,  628, "16:9", "image"),
    CreativeFormat("Display Banner",   728,   90, "8:1",  "image"),
]


class GoogleAdsAdapter(AdProvider):

    @property
    def vendor_name(self) -> str:
        return "google"

    def is_configured(self) -> bool:
        required = [
            "GOOGLE_ADS_DEVELOPER_TOKEN",
            "GOOGLE_ADS_CLIENT_ID",
            "GOOGLE_ADS_CLIENT_SECRET",
            "GOOGLE_ADS_REFRESH_TOKEN",
            "GOOGLE_ADS_CUSTOMER_ID",
        ]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            log.debug("GoogleAdsAdapter: missing env vars %s", missing)
            return False
        return True

    def _client(self):
        """Build a google-ads GoogleAdsClient from env vars."""
        try:
            from google.ads.googleads.client import GoogleAdsClient  # type: ignore
        except ImportError:
            raise RuntimeError(
                "google-ads package not installed. Run: pip install google-ads"
            )
        config = {
            "developer_token":  os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
            "client_id":        os.environ["GOOGLE_ADS_CLIENT_ID"],
            "client_secret":    os.environ["GOOGLE_ADS_CLIENT_SECRET"],
            "refresh_token":    os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
            "login_customer_id": os.environ["GOOGLE_ADS_CUSTOMER_ID"],
            "use_proto_plus":   True,
        }
        return GoogleAdsClient.load_from_dict(config)

    def create_campaign(
        self,
        name: str,
        daily_budget_usd: float,
        total_budget_usd: float | None = None,
    ) -> str:
        client = self._client()
        customer_id = os.environ["GOOGLE_ADS_CUSTOMER_ID"]

        # Create budget
        budget_service = client.get_service("CampaignBudgetService")
        budget_op = client.get_type("CampaignBudgetOperation")
        budget = budget_op.create
        budget.name = f"{name} Budget"
        budget.amount_micros = int(daily_budget_usd * 1_000_000)
        budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
        budget_response = budget_service.mutate_campaign_budgets(
            customer_id=customer_id, operations=[budget_op]
        )
        budget_resource = budget_response.results[0].resource_name

        # Create campaign
        campaign_service = client.get_service("CampaignService")
        campaign_op = client.get_type("CampaignOperation")
        campaign = campaign_op.create
        campaign.name = name
        campaign.advertising_channel_type = (
            client.enums.AdvertisingChannelTypeEnum.SEARCH
        )
        campaign.status = client.enums.CampaignStatusEnum.PAUSED  # start paused
        campaign.campaign_budget = budget_resource
        campaign_response = campaign_service.mutate_campaigns(
            customer_id=customer_id, operations=[campaign_op]
        )
        resource_name = campaign_response.results[0].resource_name
        # Extract numeric ID from resource name (customers/{id}/campaigns/{id})
        external_id = resource_name.split("/")[-1]
        log.info("GoogleAds campaign created: %s (id=%s)", name, external_id)
        return external_id

    def get_stats(self, external_id: str) -> CampaignStats:
        client = self._client()
        customer_id = os.environ["GOOGLE_ADS_CUSTOMER_ID"]
        ga_service = client.get_service("GoogleAdsService")
        query = f"""
            SELECT
              campaign.id,
              metrics.cost_micros,
              metrics.clicks,
              metrics.impressions
            FROM campaign
            WHERE campaign.id = {external_id}
        """
        response = ga_service.search(customer_id=customer_id, query=query)
        for row in response:
            spend = Decimal(row.metrics.cost_micros) / 1_000_000
            clicks = row.metrics.clicks
            impressions = row.metrics.impressions
            cpa = (spend / clicks) if clicks else None
            return CampaignStats(
                campaign_id=external_id,
                spend=spend,
                clicks=clicks,
                impressions=impressions,
                cpa=cpa,
            )
        return CampaignStats(
            campaign_id=external_id, spend=Decimal(0), clicks=0, impressions=0
        )

    def toggle_status(self, external_id: str, active: bool) -> None:
        client = self._client()
        customer_id = os.environ["GOOGLE_ADS_CUSTOMER_ID"]
        campaign_service = client.get_service("CampaignService")
        campaign_op = client.get_type("CampaignOperation")
        campaign = campaign_op.update
        campaign.resource_name = (
            f"customers/{customer_id}/campaigns/{external_id}"
        )
        status_enum = client.enums.CampaignStatusEnum
        campaign.status = status_enum.ENABLED if active else status_enum.PAUSED
        campaign_op.update_mask.paths.append("status")
        campaign_service.mutate_campaigns(
            customer_id=customer_id, operations=[campaign_op]
        )
        log.info(
            "GoogleAds campaign %s → %s", external_id, "ENABLED" if active else "PAUSED"
        )

    def get_supported_formats(self) -> list[CreativeFormat]:
        return _SUPPORTED_FORMATS
