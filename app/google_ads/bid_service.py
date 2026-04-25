import logging
from datetime import date

from app.config import settings
from app.google_ads.auth import AdsAuthManager
from app.google_ads.queries import (
    KEYWORD_PERFORMANCE_QUERY,
    DEVICE_PERFORMANCE_QUERY,
    HOURLY_PERFORMANCE_QUERY,
)

logger = logging.getLogger(__name__)


class BidService:
    def __init__(self, customer_id: str | None = None):
        self.customer_id = customer_id or settings.GOOGLE_ADS_TARGET_CUSTOMER_ID
        self.client = AdsAuthManager.get_client()
        self.ga_service = self.client.get_service("GoogleAdsService")

    def get_keyword_performance(self, date_range: str = "LAST_7_DAYS") -> list[dict]:
        query = KEYWORD_PERFORMANCE_QUERY.format(date_range=date_range)
        response = self.ga_service.search(customer_id=self.customer_id, query=query)
        rows = []
        for row in response:
            m = row.metrics
            crit = row.ad_group_criterion
            conversions = m.conversions or 0.001
            rows.append({
                "criterion_resource_name": crit.resource_name,
                "keyword_text": crit.keyword.text,
                "match_type": crit.keyword.match_type.name,
                "cpc_bid_micros": crit.cpc_bid_micros,
                "status": crit.status.name,
                "ad_group_resource_name": row.ad_group.resource_name,
                "ad_group_name": row.ad_group.name,
                "campaign_resource_name": row.campaign.resource_name,
                "campaign_name": row.campaign.name,
                "impressions": m.impressions,
                "clicks": m.clicks,
                "cost_micros": m.cost_micros,
                "conversions": m.conversions,
                "ctr": m.ctr,
                "avg_cpc_micros": m.average_cpc,
                "cpa_micros": int(m.cost_micros / conversions) if m.conversions > 0 else 0,
            })
        return rows

    def get_device_performance(self, date_range: str = "LAST_7_DAYS") -> list[dict]:
        query = DEVICE_PERFORMANCE_QUERY.format(date_range=date_range)
        response = self.ga_service.search(customer_id=self.customer_id, query=query)
        rows = []
        for row in response:
            m = row.metrics
            rows.append({
                "campaign_resource_name": row.campaign.resource_name,
                "campaign_name": row.campaign.name,
                "device": row.segments.device.name,
                "impressions": m.impressions,
                "clicks": m.clicks,
                "cost_micros": m.cost_micros,
                "conversions": m.conversions,
                "ctr": m.ctr,
            })
        return rows

    def get_hourly_performance(self, for_date: str | None = None) -> list[dict]:
        d = for_date or date.today().strftime("%Y-%m-%d")
        query = HOURLY_PERFORMANCE_QUERY.format(date=d)
        response = self.ga_service.search(customer_id=self.customer_id, query=query)
        rows = []
        for row in response:
            m = row.metrics
            rows.append({
                "campaign_resource_name": row.campaign.resource_name,
                "campaign_name": row.campaign.name,
                "hour": row.segments.hour,
                "impressions": m.impressions,
                "clicks": m.clicks,
                "cost_micros": m.cost_micros,
                "conversions": m.conversions,
            })
        return rows

    def update_keyword_bid(self, criterion_resource_name: str, new_cpc_micros: int) -> bool:
        service = self.client.get_service("AdGroupCriterionService")
        criterion = self.client.get_type("AdGroupCriterion")
        criterion.resource_name = criterion_resource_name
        criterion.cpc_bid_micros = new_cpc_micros

        op = self.client.get_type("AdGroupCriterionOperation")
        op.update.CopyFrom(criterion)
        field_mask = self.client.get_type("FieldMask")
        field_mask.paths.append("cpc_bid_micros")
        op.update_mask.CopyFrom(field_mask)

        try:
            service.mutate_ad_group_criteria(
                customer_id=self.customer_id, operations=[op]
            )
            return True
        except Exception as e:
            logger.error("Failed to update keyword bid %s: %s", criterion_resource_name, e)
            return False

    def update_campaign_bid_adjustment(
        self, campaign_resource_name: str, device: str, adjustment: float
    ) -> bool:
        service = self.client.get_service("CampaignCriterionService")
        criterion = self.client.get_type("CampaignCriterion")
        criterion.campaign = campaign_resource_name

        device_enum = self.client.enums.DeviceEnum
        device_map = {
            "MOBILE": device_enum.MOBILE,
            "TABLET": device_enum.TABLET,
            "DESKTOP": device_enum.DESKTOP,
        }
        criterion.device.type_ = device_map.get(device.upper(), device_enum.MOBILE)
        criterion.bid_modifier = adjustment

        op = self.client.get_type("CampaignCriterionOperation")
        op.create.CopyFrom(criterion)

        try:
            service.mutate_campaign_criteria(
                customer_id=self.customer_id, operations=[op]
            )
            return True
        except Exception as e:
            logger.error("Failed to update device bid adjustment: %s", e)
            return False
