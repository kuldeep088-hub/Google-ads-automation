import logging

from app.config import settings
from app.google_ads.auth import AdsAuthManager
from app.google_ads.queries import CAMPAIGN_BUDGET_QUERY

logger = logging.getLogger(__name__)


class BudgetService:
    def __init__(self, customer_id: str | None = None):
        self.customer_id = customer_id or settings.GOOGLE_ADS_TARGET_CUSTOMER_ID
        self.client = AdsAuthManager.get_client()
        self.ga_service = self.client.get_service("GoogleAdsService")

    def get_all_campaign_budgets(self) -> list[dict]:
        response = self.ga_service.search(
            customer_id=self.customer_id, query=CAMPAIGN_BUDGET_QUERY
        )
        rows = []
        for row in response:
            rows.append({
                "campaign_resource_name": row.campaign.resource_name,
                "campaign_id": row.campaign.id,
                "campaign_name": row.campaign.name,
                "campaign_status": row.campaign.status.name,
                "budget_resource_name": row.campaign_budget.resource_name,
                "daily_budget_micros": row.campaign_budget.amount_micros,
                "cost_micros_this_month": row.metrics.cost_micros,
            })
        return rows

    def update_budget(self, budget_resource_name: str, new_daily_budget_micros: int) -> bool:
        service = self.client.get_service("CampaignBudgetService")
        budget = self.client.get_type("CampaignBudget")
        budget.resource_name = budget_resource_name
        budget.amount_micros = new_daily_budget_micros

        op = self.client.get_type("CampaignBudgetOperation")
        op.update.CopyFrom(budget)
        field_mask = self.client.get_type("FieldMask")
        field_mask.paths.append("amount_micros")
        op.update_mask.CopyFrom(field_mask)

        try:
            service.mutate_campaign_budgets(
                customer_id=self.customer_id, operations=[op]
            )
            return True
        except Exception as e:
            logger.error("Failed to update budget %s: %s", budget_resource_name, e)
            return False

    def pause_campaign(self, campaign_resource_name: str) -> bool:
        return self._set_campaign_status(campaign_resource_name, "PAUSED")

    def enable_campaign(self, campaign_resource_name: str) -> bool:
        return self._set_campaign_status(campaign_resource_name, "ENABLED")

    def _set_campaign_status(self, campaign_resource_name: str, status: str) -> bool:
        service = self.client.get_service("CampaignService")
        campaign = self.client.get_type("Campaign")
        campaign.resource_name = campaign_resource_name

        status_enum = self.client.enums.CampaignStatusEnum
        campaign.status = getattr(status_enum, status)

        op = self.client.get_type("CampaignOperation")
        op.update.CopyFrom(campaign)
        field_mask = self.client.get_type("FieldMask")
        field_mask.paths.append("status")
        op.update_mask.CopyFrom(field_mask)

        try:
            service.mutate_campaigns(customer_id=self.customer_id, operations=[op])
            return True
        except Exception as e:
            logger.error("Failed to set campaign status %s → %s: %s", campaign_resource_name, status, e)
            return False
