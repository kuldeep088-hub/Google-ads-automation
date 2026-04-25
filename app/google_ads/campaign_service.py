import logging
from dataclasses import dataclass, field

from app.config import settings
from app.google_ads.auth import AdsAuthManager

logger = logging.getLogger(__name__)

MICROS = 1_000_000


@dataclass
class CampaignRow:
    campaign_name: str
    campaign_type: str
    daily_budget_usd: float
    bid_strategy: str
    ad_group_name: str
    keywords: list[tuple[str, str]]
    headline_1: str
    headline_2: str
    headline_3: str
    description_1: str
    description_2: str
    final_url: str
    geo_target: str = "US"
    language: str = "en"


@dataclass
class BulkCreateResult:
    row_index: int
    campaign_name: str
    success: bool
    campaign_resource: str = ""
    error: str = ""


class CampaignService:
    def __init__(self, customer_id: str | None = None):
        self.customer_id = customer_id or settings.GOOGLE_ADS_TARGET_CUSTOMER_ID
        self.client = AdsAuthManager.get_client()

    def create_campaign(self, row: CampaignRow) -> str:
        budget_resource = self._create_budget(row.daily_budget_usd)
        campaign = self.client.get_type("Campaign")
        campaign.name = row.campaign_name
        campaign.status = self.client.enums.CampaignStatusEnum.PAUSED

        adv_channel_map = {
            "SEARCH": self.client.enums.AdvertisingChannelTypeEnum.SEARCH,
            "DISPLAY": self.client.enums.AdvertisingChannelTypeEnum.DISPLAY,
        }
        campaign.advertising_channel_type = adv_channel_map.get(
            row.campaign_type.upper(),
            self.client.enums.AdvertisingChannelTypeEnum.SEARCH,
        )

        if row.bid_strategy.upper() == "MANUAL_CPC":
            campaign.manual_cpc.enhanced_cpc_enabled = False
        elif row.bid_strategy.upper() == "MAXIMIZE_CONVERSIONS":
            campaign.maximize_conversions.target_cpa_micros = 0

        campaign.campaign_budget = budget_resource

        network_settings = self.client.get_type("Campaign.NetworkSettings")
        network_settings.target_google_search = True
        network_settings.target_search_network = True
        campaign.network_settings.CopyFrom(network_settings)

        op = self.client.get_type("CampaignOperation")
        op.create.CopyFrom(campaign)

        service = self.client.get_service("CampaignService")
        response = service.mutate_campaigns(customer_id=self.customer_id, operations=[op])
        resource_name = response.results[0].resource_name
        logger.info("Created campaign: %s", resource_name)
        return resource_name

    def _create_budget(self, daily_budget_usd: float) -> str:
        service = self.client.get_service("CampaignBudgetService")
        budget = self.client.get_type("CampaignBudget")
        budget.amount_micros = int(daily_budget_usd * MICROS)
        budget.delivery_method = self.client.enums.BudgetDeliveryMethodEnum.STANDARD

        op = self.client.get_type("CampaignBudgetOperation")
        op.create.CopyFrom(budget)
        response = service.mutate_campaign_budgets(customer_id=self.customer_id, operations=[op])
        return response.results[0].resource_name

    def create_ad_group(self, row: CampaignRow, campaign_resource_name: str) -> str:
        service = self.client.get_service("AdGroupService")
        ad_group = self.client.get_type("AdGroup")
        ad_group.name = row.ad_group_name
        ad_group.campaign = campaign_resource_name
        ad_group.status = self.client.enums.AdGroupStatusEnum.ENABLED
        ad_group.type_ = self.client.enums.AdGroupTypeEnum.SEARCH_STANDARD

        op = self.client.get_type("AdGroupOperation")
        op.create.CopyFrom(ad_group)
        response = service.mutate_ad_groups(customer_id=self.customer_id, operations=[op])
        resource_name = response.results[0].resource_name
        logger.info("Created ad group: %s", resource_name)
        return resource_name

    def create_responsive_search_ad(self, row: CampaignRow, ad_group_resource_name: str) -> str:
        service = self.client.get_service("AdGroupAdService")
        ad_group_ad = self.client.get_type("AdGroupAd")
        ad_group_ad.ad_group = ad_group_resource_name
        ad_group_ad.status = self.client.enums.AdGroupAdStatusEnum.ENABLED

        ad = ad_group_ad.ad
        ad.final_urls.append(row.final_url)

        rsa = ad.responsive_search_ad
        for headline_text in [row.headline_1, row.headline_2, row.headline_3]:
            headline = self.client.get_type("AdTextAsset")
            headline.text = headline_text[:30]
            rsa.headlines.append(headline)

        for desc_text in [row.description_1, row.description_2]:
            desc = self.client.get_type("AdTextAsset")
            desc.text = desc_text[:90]
            rsa.descriptions.append(desc)

        op = self.client.get_type("AdGroupAdOperation")
        op.create.CopyFrom(ad_group_ad)
        response = service.mutate_ad_group_ads(customer_id=self.customer_id, operations=[op])
        return response.results[0].resource_name

    def create_keyword(self, keyword_text: str, match_type: str, ad_group_resource_name: str) -> str:
        service = self.client.get_service("AdGroupCriterionService")
        criterion = self.client.get_type("AdGroupCriterion")
        criterion.ad_group = ad_group_resource_name
        criterion.status = self.client.enums.AdGroupCriterionStatusEnum.ENABLED
        criterion.keyword.text = keyword_text

        match_map = {
            "BROAD": self.client.enums.KeywordMatchTypeEnum.BROAD,
            "PHRASE": self.client.enums.KeywordMatchTypeEnum.PHRASE,
            "EXACT": self.client.enums.KeywordMatchTypeEnum.EXACT,
        }
        criterion.keyword.match_type = match_map.get(match_type.upper(), self.client.enums.KeywordMatchTypeEnum.BROAD)

        op = self.client.get_type("AdGroupCriterionOperation")
        op.create.CopyFrom(criterion)
        response = service.mutate_ad_group_criteria(customer_id=self.customer_id, operations=[op])
        return response.results[0].resource_name

    def bulk_create_from_rows(self, rows: list[CampaignRow]) -> list[BulkCreateResult]:
        results = []
        for idx, row in enumerate(rows):
            try:
                campaign_resource = self.create_campaign(row)
                ad_group_resource = self.create_ad_group(row, campaign_resource)
                self.create_responsive_search_ad(row, ad_group_resource)
                for kw_text, kw_match in row.keywords:
                    self.create_keyword(kw_text, kw_match, ad_group_resource)
                results.append(BulkCreateResult(
                    row_index=idx,
                    campaign_name=row.campaign_name,
                    success=True,
                    campaign_resource=campaign_resource,
                ))
            except Exception as e:
                logger.error("Failed to create campaign %s: %s", row.campaign_name, e)
                results.append(BulkCreateResult(
                    row_index=idx,
                    campaign_name=row.campaign_name,
                    success=False,
                    error=str(e),
                ))
        return results
