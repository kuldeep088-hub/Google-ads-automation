import logging
from app.config import settings
from app.google_ads.auth import AdsAuthManager
from app.google_ads.queries import QUALITY_SCORE_QUERY

logger = logging.getLogger(__name__)
MICROS = 1_000_000


class QualityScoreService:
    def __init__(self, customer_id: str | None = None):
        self.customer_id = customer_id or settings.GOOGLE_ADS_TARGET_CUSTOMER_ID
        self.client = AdsAuthManager.get_client()
        self.ga_service = self.client.get_service("GoogleAdsService")

    def get_all_keyword_quality_scores(self) -> list[dict]:
        response = self.ga_service.search(customer_id=self.customer_id, query=QUALITY_SCORE_QUERY)
        rows = []
        for row in response:
            crit = row.ad_group_criterion
            qi = crit.quality_info
            m = row.metrics
            rows.append({
                "criterion_resource": crit.resource_name,
                "keyword_text": crit.keyword.text,
                "match_type": crit.keyword.match_type.name,
                "cpc_bid_micros": crit.cpc_bid_micros,
                "quality_score": qi.quality_score if qi.quality_score else None,
                "creative_quality": qi.creative_quality_score.name if qi.creative_quality_score else None,
                "landing_page_quality": qi.post_click_quality_score.name if qi.post_click_quality_score else None,
                "expected_ctr": qi.search_predicted_ctr.name if qi.search_predicted_ctr else None,
                "ad_group_resource": row.ad_group.resource_name,
                "ad_group_name": row.ad_group.name,
                "campaign_resource": row.campaign.resource_name,
                "campaign_name": row.campaign.name,
                "clicks": m.clicks,
                "cost_micros": m.cost_micros,
                "cost_usd": m.cost_micros / MICROS,
                "conversions": m.conversions,
                "impressions": m.impressions,
            })
        return rows

    def pause_keyword(self, criterion_resource: str) -> bool:
        service = self.client.get_service("AdGroupCriterionService")
        criterion = self.client.get_type("AdGroupCriterion")
        criterion.resource_name = criterion_resource
        criterion.status = self.client.enums.AdGroupCriterionStatusEnum.PAUSED

        op = self.client.get_type("AdGroupCriterionOperation")
        op.update.CopyFrom(criterion)
        field_mask = self.client.get_type("FieldMask")
        field_mask.paths.append("status")
        op.update_mask.CopyFrom(field_mask)

        try:
            service.mutate_ad_group_criteria(customer_id=self.customer_id, operations=[op])
            logger.info("Paused low-QS keyword: %s", criterion_resource)
            return True
        except Exception as e:
            logger.error("Failed to pause keyword %s: %s", criterion_resource, e)
            return False
