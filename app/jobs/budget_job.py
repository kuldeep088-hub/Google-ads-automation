import json
import logging
from datetime import datetime

from app.database import SessionLocal
from app.db.models import JobRun, BudgetMonthlyCap
from app.automation.rule_engine import RuleEngine
from app.google_ads.budget_service import BudgetService
from app.config import settings

logger = logging.getLogger(__name__)

MICROS = 1_000_000


def run_budget_management(triggered_by: str = "scheduler"):
    db = SessionLocal()
    job_run = JobRun(
        job_name="budget_management",
        status="running",
        started_at=datetime.utcnow(),
        triggered_by=triggered_by,
    )
    db.add(job_run)
    db.commit()

    paused_campaigns = []

    try:
        budget_service = BudgetService()
        campaigns = budget_service.get_all_campaign_budgets()

        month_year = datetime.utcnow().strftime("%Y-%m")
        for camp in campaigns:
            cap = (
                db.query(BudgetMonthlyCap)
                .filter(
                    BudgetMonthlyCap.campaign_resource == camp["campaign_resource_name"],
                    BudgetMonthlyCap.month_year == month_year,
                )
                .first()
            )
            if cap:
                cap.spent_micros = camp["cost_micros_this_month"]
                cap.last_checked_at = datetime.utcnow()
                db.commit()

                if cap.spent_micros >= cap.cap_micros and not cap.is_paused_by_cap:
                    budget_service.pause_campaign(camp["campaign_resource_name"])
                    cap.is_paused_by_cap = True
                    db.commit()
                    paused_campaigns.append(camp["campaign_name"])
                    logger.info("Paused campaign %s — monthly cap reached", camp["campaign_name"])

        engine = RuleEngine(db=db)
        result = engine.run("budget_cap")
        result += engine.run("budget_pause")

        job_run.status = "success"
        job_run.rules_evaluated = result.rules_evaluated
        job_run.actions_taken = result.actions_taken
        job_run.errors_count = result.errors_count

        if paused_campaigns:
            _send_pause_alert(paused_campaigns)

    except Exception as exc:
        job_run.status = "failed"
        job_run.error_summary = json.dumps([str(exc)])
        logger.exception("budget_management job failed")
    finally:
        job_run.finished_at = datetime.utcnow()
        db.commit()
        db.close()


def _send_pause_alert(campaign_names: list[str]):
    try:
        from app.notifications.slack_sender import SlackSender
        names = ", ".join(campaign_names)
        SlackSender().send(f":pause_button: Campaigns paused (monthly cap reached): {names}")
    except Exception:
        pass
