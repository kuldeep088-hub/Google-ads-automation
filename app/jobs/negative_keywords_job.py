import json
import logging
from datetime import datetime, date

from app.database import SessionLocal
from app.db.models import JobRun, NegativeKeywordAdded, SearchTermSnapshot

logger = logging.getLogger(__name__)

WASTE_CLICKS_THRESHOLD = 5
WASTE_COST_USD_THRESHOLD = 2.0
MICROS = 1_000_000


def run_negative_keyword_mining(triggered_by: str = "scheduler"):
    db = SessionLocal()
    job_run = JobRun(
        job_name="negative_keyword_mining",
        status="running",
        started_at=datetime.utcnow(),
        triggered_by=triggered_by,
    )
    db.add(job_run)
    db.commit()

    actions_taken = 0
    errors = []

    try:
        from app.google_ads.search_term_service import SearchTermService
        svc = SearchTermService()
        terms = svc.get_search_terms(date_range="LAST_30_DAYS")

        already_added = {
            (r.keyword_text.lower(), r.campaign_resource)
            for r in db.query(NegativeKeywordAdded).all()
        }

        for t in terms:
            clicks = t.get("clicks", 0)
            conversions = t.get("conversions", 0)
            cost_usd = t.get("cost_usd", 0)
            term_text = t.get("search_term", "").strip()
            campaign_resource = t.get("campaign_resource", "")

            is_waste = (
                conversions == 0
                and (clicks >= WASTE_CLICKS_THRESHOLD or cost_usd >= WASTE_COST_USD_THRESHOLD)
            )
            if not is_waste:
                continue
            if (term_text.lower(), campaign_resource) in already_added:
                continue

            success = svc.add_negative_keyword(term_text, campaign_resource, match_type="BROAD")
            if success:
                db.add(NegativeKeywordAdded(
                    keyword_text=term_text,
                    match_type="BROAD",
                    campaign_resource=campaign_resource,
                    campaign_name=t.get("campaign_name"),
                    reason="zero_conversions_waste",
                    clicks_wasted=clicks,
                    cost_wasted_micros=int(cost_usd * MICROS),
                ))
                already_added.add((term_text.lower(), campaign_resource))
                actions_taken += 1

        # Snapshot today's search terms for historical tracking
        today = date.today()
        for t in terms:
            existing = db.query(SearchTermSnapshot).filter(
                SearchTermSnapshot.snapshot_date == today,
                SearchTermSnapshot.search_term == t.get("search_term", ""),
                SearchTermSnapshot.ad_group_resource == t.get("ad_group_resource", ""),
            ).first()
            if not existing:
                db.add(SearchTermSnapshot(
                    snapshot_date=today,
                    search_term=t.get("search_term", ""),
                    ad_group_resource=t.get("ad_group_resource", ""),
                    ad_group_name=t.get("ad_group_name"),
                    campaign_resource=t.get("campaign_resource", ""),
                    campaign_name=t.get("campaign_name"),
                    impressions=t.get("impressions", 0),
                    clicks=t.get("clicks", 0),
                    cost_micros=int(t.get("cost_usd", 0) * MICROS),
                    conversions=t.get("conversions", 0),
                    ctr=t.get("ctr", 0),
                    avg_cpc_micros=t.get("avg_cpc_micros", 0),
                ))

        db.commit()
        job_run.status = "success"
        job_run.actions_taken = actions_taken
        logger.info("Negative keyword mining: %d keywords added as negatives", actions_taken)

    except Exception as exc:
        db.rollback()
        job_run.status = "failed"
        job_run.errors_count = 1
        job_run.error_summary = json.dumps([str(exc)])
        logger.exception("negative_keyword_mining job failed")
        _send_failure_alert("negative_keyword_mining", str(exc))
    finally:
        job_run.finished_at = datetime.utcnow()
        db.commit()
        db.close()


def _send_failure_alert(job_name: str, error: str):
    try:
        from app.notifications.slack_sender import SlackSender
        SlackSender().send(f":red_circle: *{job_name}* job failed: {error}")
    except Exception:
        pass
