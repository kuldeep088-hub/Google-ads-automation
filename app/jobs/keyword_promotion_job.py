import json
import logging
from datetime import datetime

from app.database import SessionLocal
from app.db.models import JobRun, PromotedKeyword

logger = logging.getLogger(__name__)

PROMOTE_MIN_CONVERSIONS = 2
PROMOTE_MIN_CLICKS = 10
MICROS = 1_000_000


def run_keyword_promotion(triggered_by: str = "scheduler"):
    db = SessionLocal()
    job_run = JobRun(
        job_name="keyword_promotion",
        status="running",
        started_at=datetime.utcnow(),
        triggered_by=triggered_by,
    )
    db.add(job_run)
    db.commit()

    actions_taken = 0

    try:
        from app.google_ads.search_term_service import SearchTermService
        from app.ml.bid_predictor import predict_optimal_bid

        svc = SearchTermService()
        terms = svc.get_search_terms(date_range="LAST_30_DAYS")

        already_promoted = {
            (r.search_term.lower(), r.ad_group_resource)
            for r in db.query(PromotedKeyword).all()
        }

        for t in terms:
            conversions = t.get("conversions", 0)
            clicks = t.get("clicks", 0)
            term_text = t.get("search_term", "").strip()
            ad_group_resource = t.get("ad_group_resource", "")

            if conversions < PROMOTE_MIN_CONVERSIONS and clicks < PROMOTE_MIN_CLICKS:
                continue
            if (term_text.lower(), ad_group_resource) in already_promoted:
                continue
            # Skip terms that look like they are already keywords (exact match status)
            if t.get("status") == "ADDED":
                continue

            # Use ML to set an appropriate opening bid
            bid_result = predict_optimal_bid(t)
            bid_micros = bid_result.get("predicted_bid_micros")

            resource = svc.promote_to_keyword(
                term_text,
                ad_group_resource,
                match_type="EXACT",
                bid_micros=bid_micros,
            )
            if resource:
                db.add(PromotedKeyword(
                    search_term=term_text,
                    ad_group_resource=ad_group_resource,
                    ad_group_name=t.get("ad_group_name"),
                    campaign_name=t.get("campaign_name"),
                    conversions=conversions,
                    clicks=clicks,
                    cost_micros=int(t.get("cost_usd", 0) * MICROS),
                    criterion_resource=resource,
                ))
                already_promoted.add((term_text.lower(), ad_group_resource))
                actions_taken += 1

        db.commit()
        job_run.status = "success"
        job_run.actions_taken = actions_taken
        logger.info("Keyword promotion: %d search terms promoted to keywords", actions_taken)

    except Exception as exc:
        db.rollback()
        job_run.status = "failed"
        job_run.errors_count = 1
        job_run.error_summary = json.dumps([str(exc)])
        logger.exception("keyword_promotion job failed")
        _send_failure_alert("keyword_promotion", str(exc))
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
