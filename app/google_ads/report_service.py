import logging
from datetime import date, timedelta

from app.config import settings
from app.google_ads.auth import AdsAuthManager
from app.google_ads.queries import (
    CAMPAIGN_PERFORMANCE_QUERY,
    KEYWORD_PERFORMANCE_QUERY,
    ACCOUNT_SUMMARY_QUERY,
)

logger = logging.getLogger(__name__)

MICROS = 1_000_000


class ReportService:
    def __init__(self, customer_id: str | None = None):
        self.customer_id = customer_id or settings.GOOGLE_ADS_TARGET_CUSTOMER_ID
        self.client = AdsAuthManager.get_client()
        self.ga_service = self.client.get_service("GoogleAdsService")

    def get_daily_summary(self, for_date: str | None = None) -> dict:
        d = for_date or date.today().strftime("%Y-%m-%d")
        query = ACCOUNT_SUMMARY_QUERY.format(date_range=f"DURING '{d}'")
        response = self.ga_service.search(customer_id=self.customer_id, query=query)
        totals = {"impressions": 0, "clicks": 0, "cost_micros": 0, "conversions": 0.0, "ctr": 0.0, "avg_cpc_micros": 0}
        count = 0
        for row in response:
            m = row.metrics
            totals["impressions"] += m.impressions
            totals["clicks"] += m.clicks
            totals["cost_micros"] += m.cost_micros
            totals["conversions"] += m.conversions
            totals["ctr"] += m.ctr
            totals["avg_cpc_micros"] += m.average_cpc
            count += 1
        if count > 1:
            totals["ctr"] /= count
            totals["avg_cpc_micros"] /= count
        totals["cost_usd"] = totals["cost_micros"] / MICROS
        totals["cpa_usd"] = (totals["cost_micros"] / MICROS) / max(totals["conversions"], 0.001)
        totals["date"] = d
        return totals

    def get_campaign_performance(self, date_range: str = "LAST_7_DAYS") -> list[dict]:
        query = CAMPAIGN_PERFORMANCE_QUERY.format(date_range=date_range)
        response = self.ga_service.search(customer_id=self.customer_id, query=query)
        rows = []
        for row in response:
            m = row.metrics
            conv = m.conversions or 0.001
            rows.append({
                "campaign_resource_name": row.campaign.resource_name,
                "campaign_id": row.campaign.id,
                "campaign_name": row.campaign.name,
                "status": row.campaign.status.name,
                "budget_micros": row.campaign_budget.amount_micros,
                "budget_usd": row.campaign_budget.amount_micros / MICROS,
                "impressions": m.impressions,
                "clicks": m.clicks,
                "cost_micros": m.cost_micros,
                "cost_usd": m.cost_micros / MICROS,
                "conversions": m.conversions,
                "ctr": round(m.ctr * 100, 2),
                "avg_cpc_usd": m.average_cpc / MICROS,
                "cpa_usd": (m.cost_micros / MICROS) / conv if m.conversions > 0 else 0,
            })
        return rows

    def get_keyword_performance(self, date_range: str = "LAST_7_DAYS") -> list[dict]:
        query = KEYWORD_PERFORMANCE_QUERY.format(date_range=date_range)
        response = self.ga_service.search(customer_id=self.customer_id, query=query)
        rows = []
        for row in response:
            m = row.metrics
            rows.append({
                "keyword": row.ad_group_criterion.keyword.text,
                "match_type": row.ad_group_criterion.keyword.match_type.name,
                "campaign_name": row.campaign.name,
                "ad_group_name": row.ad_group.name,
                "impressions": m.impressions,
                "clicks": m.clicks,
                "cost_usd": m.cost_micros / MICROS,
                "conversions": m.conversions,
                "ctr": round(m.ctr * 100, 2),
                "avg_cpc_usd": m.average_cpc / MICROS,
            })
        return rows

    def get_top_anomalies(self, threshold_pct: float = 0.30) -> list[dict]:
        today_summary = self.get_daily_summary()
        week_campaigns = self.get_campaign_performance("LAST_7_DAYS")

        anomalies = []
        if not week_campaigns:
            return anomalies

        total_cost_7d = sum(r["cost_usd"] for r in week_campaigns)
        avg_daily_cost = total_cost_7d / 7
        today_cost = today_summary.get("cost_usd", 0)

        if avg_daily_cost > 0:
            deviation = abs(today_cost - avg_daily_cost) / avg_daily_cost
            if deviation > threshold_pct:
                direction = "spike" if today_cost > avg_daily_cost else "drop"
                anomalies.append({
                    "metric": "daily_spend",
                    "direction": direction,
                    "today_value": round(today_cost, 2),
                    "avg_value": round(avg_daily_cost, 2),
                    "deviation_pct": round(deviation * 100, 1),
                })

        return anomalies
