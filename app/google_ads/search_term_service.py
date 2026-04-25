import logging
from app.config import settings
from app.google_ads.auth import AdsAuthManager
from app.google_ads.queries import SEARCH_TERMS_QUERY

logger = logging.getLogger(__name__)
MICROS = 1_000_000


class SearchTermService:
    def __init__(self, customer_id: str | None = None):
        self.customer_id = customer_id or settings.GOOGLE_ADS_TARGET_CUSTOMER_ID
        self.client = AdsAuthManager.get_client()
        self.ga_service = self.client.get_service("GoogleAdsService")

    def get_search_terms(self, date_range: str = "LAST_30_DAYS") -> list[dict]:
        query = SEARCH_TERMS_QUERY.format(date_range=date_range)
        response = self.ga_service.search(customer_id=self.customer_id, query=query)
        rows = []
        for row in response:
            m = row.metrics
            rows.append({
                "search_term": row.search_term_view.search_term,
                "status": row.search_term_view.status.name,
                "ad_group_resource": row.ad_group.resource_name,
                "ad_group_name": row.ad_group.name,
                "campaign_resource": row.campaign.resource_name,
                "campaign_name": row.campaign.name,
                "impressions": m.impressions,
                "clicks": m.clicks,
                "cost_micros": m.cost_micros,
                "cost_usd": m.cost_micros / MICROS,
                "conversions": m.conversions,
                "ctr": m.ctr,
                "avg_cpc_micros": m.average_cpc,
            })
        return rows

    def add_negative_keyword(
        self,
        keyword_text: str,
        campaign_resource: str,
        match_type: str = "BROAD",
    ) -> bool:
        service = self.client.get_service("CampaignCriterionService")
        criterion = self.client.get_type("CampaignCriterion")
        criterion.campaign = campaign_resource
        criterion.negative = True
        criterion.keyword.text = keyword_text

        match_map = {
            "BROAD": self.client.enums.KeywordMatchTypeEnum.BROAD,
            "PHRASE": self.client.enums.KeywordMatchTypeEnum.PHRASE,
            "EXACT": self.client.enums.KeywordMatchTypeEnum.EXACT,
        }
        criterion.keyword.match_type = match_map.get(match_type.upper(), self.client.enums.KeywordMatchTypeEnum.BROAD)

        op = self.client.get_type("CampaignCriterionOperation")
        op.create.CopyFrom(criterion)
        try:
            service.mutate_campaign_criteria(customer_id=self.customer_id, operations=[op])
            logger.info("Added negative keyword '%s' to campaign %s", keyword_text, campaign_resource)
            return True
        except Exception as e:
            logger.error("Failed to add negative keyword '%s': %s", keyword_text, e)
            return False

    def promote_to_keyword(
        self,
        search_term: str,
        ad_group_resource: str,
        match_type: str = "EXACT",
        bid_micros: int | None = None,
    ) -> str | None:
        service = self.client.get_service("AdGroupCriterionService")
        criterion = self.client.get_type("AdGroupCriterion")
        criterion.ad_group = ad_group_resource
        criterion.status = self.client.enums.AdGroupCriterionStatusEnum.ENABLED
        criterion.keyword.text = search_term

        match_map = {
            "BROAD": self.client.enums.KeywordMatchTypeEnum.BROAD,
            "PHRASE": self.client.enums.KeywordMatchTypeEnum.PHRASE,
            "EXACT": self.client.enums.KeywordMatchTypeEnum.EXACT,
        }
        criterion.keyword.match_type = match_map.get(match_type.upper(), self.client.enums.KeywordMatchTypeEnum.EXACT)

        if bid_micros:
            criterion.cpc_bid_micros = bid_micros

        op = self.client.get_type("AdGroupCriterionOperation")
        op.create.CopyFrom(criterion)
        try:
            response = service.mutate_ad_group_criteria(customer_id=self.customer_id, operations=[op])
            resource = response.results[0].resource_name
            logger.info("Promoted search term '%s' to keyword in %s", search_term, ad_group_resource)
            return resource
        except Exception as e:
            logger.error("Failed to promote search term '%s': %s", search_term, e)
            return None
