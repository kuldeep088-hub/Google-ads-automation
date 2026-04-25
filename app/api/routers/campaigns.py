import json
import logging
import os
import tempfile
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import CampaignCreationBatch

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.endswith(".csv"):
        return JSONResponse({"error": "Only CSV files accepted"}, status_code=400)

    content = await file.read()
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".csv", mode="wb", dir="."
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    from app.ingestion.csv_parser import parse_campaign_csv
    rows, errors = parse_campaign_csv(tmp_path)

    batch = CampaignCreationBatch(
        source_type="csv",
        source_ref=tmp_path,
        total_rows=len(rows) + len(errors),
        failure_count=len(errors),
        status="pending" if rows else "partial_failure",
    )
    db.add(batch)
    db.commit()

    if rows:
        from app.jobs.campaign_job import _process_batch
        import threading
        threading.Thread(target=_process_batch, args=(db, batch), daemon=True).start()

    return {
        "batch_id": batch.id,
        "total_rows": batch.total_rows,
        "valid_rows": len(rows),
        "parse_errors": errors,
        "status": batch.status,
    }


@router.post("/sheets")
async def import_sheets(
    sheet_url: str = Form(...),
    db: Session = Depends(get_db),
):
    from app.config import settings
    from app.ingestion.sheets_parser import fetch_from_google_sheets

    creds_path = settings.GSPREAD_SERVICE_ACCOUNT_JSON
    if not os.path.exists(creds_path):
        return JSONResponse(
            {"error": f"Google Sheets credentials not found at {creds_path}"},
            status_code=400,
        )

    rows, errors = fetch_from_google_sheets(sheet_url, creds_path)
    batch = CampaignCreationBatch(
        source_type="google_sheets",
        source_ref=sheet_url,
        total_rows=len(rows) + len(errors),
        failure_count=len(errors),
        status="pending" if rows else "partial_failure",
    )
    db.add(batch)
    db.commit()

    if rows:
        from app.jobs.campaign_job import _process_batch
        import threading
        threading.Thread(target=_process_batch, args=(db, batch), daemon=True).start()

    return {
        "batch_id": batch.id,
        "total_rows": batch.total_rows,
        "valid_rows": len(rows),
        "parse_errors": errors,
        "status": batch.status,
    }


@router.get("/batches")
async def list_batches(db: Session = Depends(get_db)):
    batches = (
        db.query(CampaignCreationBatch)
        .order_by(CampaignCreationBatch.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": b.id,
            "source_type": b.source_type,
            "source_ref": b.source_ref,
            "total_rows": b.total_rows,
            "success_count": b.success_count,
            "failure_count": b.failure_count,
            "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches
    ]


@router.get("/batches/{batch_id}")
async def get_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(CampaignCreationBatch).get(batch_id)
    if not batch:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {
        "id": batch.id,
        "status": batch.status,
        "success_count": batch.success_count,
        "failure_count": batch.failure_count,
        "results": json.loads(batch.results) if batch.results else [],
    }
