import json
import logging
from datetime import datetime

from app.database import SessionLocal
from app.db.models import JobRun, CampaignCreationBatch

logger = logging.getLogger(__name__)


def run_pending_campaign_batches(triggered_by: str = "scheduler"):
    db = SessionLocal()
    try:
        pending = (
            db.query(CampaignCreationBatch)
            .filter(CampaignCreationBatch.status == "pending")
            .all()
        )
        for batch in pending:
            _process_batch(db, batch)
    finally:
        db.close()


def _process_batch(db, batch: CampaignCreationBatch):
    from app.ingestion.csv_parser import parse_campaign_csv
    from app.google_ads.campaign_service import CampaignService

    batch.status = "processing"
    db.commit()

    try:
        rows, errors = parse_campaign_csv(batch.source_ref)
        service = CampaignService()
        results = service.bulk_create_from_rows(rows)

        success_count = sum(1 for r in results if r.success)
        failure_count = sum(1 for r in results if not r.success)

        batch.success_count = success_count
        batch.failure_count = failure_count + len(errors)
        batch.status = "completed" if failure_count == 0 else "partial_failure"
        batch.results = json.dumps([
            {
                "row": r.row_index,
                "campaign": r.campaign_name,
                "success": r.success,
                "resource": r.campaign_resource,
                "error": r.error,
            }
            for r in results
        ])
        batch.finished_at = datetime.utcnow()
        db.commit()
        logger.info("Batch %d: %d success, %d failure", batch.id, success_count, failure_count)
    except Exception as e:
        batch.status = "partial_failure"
        batch.error_summary = str(e)
        batch.finished_at = datetime.utcnow()
        db.commit()
        logger.exception("Batch %d failed", batch.id)
