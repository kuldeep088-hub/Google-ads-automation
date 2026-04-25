import json
import logging
from datetime import datetime, date

from app.database import SessionLocal
from app.db.models import JobRun, QualityScoreHistory

logger = logging.getLogger(__name__)

AUTO_PAUSE_QS_THRESHOLD = 3   # pause keywords with QS <= this
AUTO_PAUSE_MIN_CLICKS = 5     # only if they have enough data


def run_quality_score_monitor(triggered_by: str = "scheduler"):
    db = SessionLocal()
    job_run = JobRun(
        job_name="quality_score_monitor",
        status="running",
        started_at=datetime.utcnow(),
        triggered_by=triggered_by,
    )
    db.add(job_run)
    db.commit()

    actions_taken = 0
    paused_keywords = []

    try:
        from app.google_ads.quality_score_service import QualityScoreService
        svc = QualityScoreService()
        keywords = svc.get_all_keyword_quality_scores()
        today = date.today()

        for kw in keywords:
            qs = kw.get("quality_score")
            clicks = kw.get("clicks", 0)
            criterion_resource = kw["criterion_resource"]

            # Upsert snapshot
            existing = db.query(QualityScoreHistory).filter(
                QualityScoreHistory.snapshot_date == today,
                QualityScoreHistory.criterion_resource == criterion_resource,
            ).first()

            auto_paused = False
            should_pause = (
                qs is not None
                and qs <= AUTO_PAUSE_QS_THRESHOLD
                and clicks >= AUTO_PAUSE_MIN_CLICKS
            )
            if should_pause and (existing is None or not existing.auto_paused):
                paused = svc.pause_keyword(criterion_resource)
                if paused:
                    auto_paused = True
                    actions_taken += 1
                    paused_keywords.append(
                        f"{kw.get('keyword_text')} (QS={qs}, campaign={kw.get('campaign_name')})"
                    )

            record_data = dict(
                snapshot_date=today,
                criterion_resource=criterion_resource,
                keyword_text=kw.get("keyword_text", ""),
                match_type=kw.get("match_type"),
                quality_score=qs,
                creative_quality=kw.get("creative_quality"),
                landing_page_quality=kw.get("landing_page_quality"),
                expected_ctr=kw.get("expected_ctr"),
                cpc_bid_micros=kw.get("cpc_bid_micros", 0),
                clicks=clicks,
                cost_micros=kw.get("cost_micros", 0),
                ad_group_name=kw.get("ad_group_name"),
                campaign_name=kw.get("campaign_name"),
                campaign_resource=kw.get("campaign_resource"),
                auto_paused=auto_paused,
            )
            if existing:
                for k, v in record_data.items():
                    setattr(existing, k, v)
            else:
                db.add(QualityScoreHistory(**record_data))

        db.commit()
        job_run.status = "success"
        job_run.actions_taken = actions_taken
        job_run.rules_evaluated = len(keywords)

        if paused_keywords:
            _send_pause_alert(paused_keywords)

        logger.info(
            "Quality score monitor: %d keywords scanned, %d auto-paused",
            len(keywords), actions_taken,
        )

    except Exception as exc:
        db.rollback()
        job_run.status = "failed"
        job_run.errors_count = 1
        job_run.error_summary = json.dumps([str(exc)])
        logger.exception("quality_score_monitor job failed")
        _send_failure_alert("quality_score_monitor", str(exc))
    finally:
        job_run.finished_at = datetime.utcnow()
        db.commit()
        db.close()


def _send_pause_alert(paused: list[str]):
    try:
        from app.notifications.slack_sender import SlackSender
        body = "\n".join(f"• {k}" for k in paused)
        SlackSender().send(
            f":warning: *Quality Score Monitor* auto-paused {len(paused)} low-QS keywords:\n{body}"
        )
    except Exception:
        pass


def _send_failure_alert(job_name: str, error: str):
    try:
        from app.notifications.slack_sender import SlackSender
        SlackSender().send(f":red_circle: *{job_name}* job failed: {error}")
    except Exception:
        pass
