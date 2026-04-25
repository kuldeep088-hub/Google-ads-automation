import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import AuditLog, JobRun

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

JOB_REGISTRY = {
    "bid_management": "app.jobs.bid_job.run_bid_management",
    "tod_bid_rules": "app.jobs.bid_job.run_tod_bid_rules",
    "budget_management": "app.jobs.budget_job.run_budget_management",
    "daily_reporting": "app.jobs.report_job.run_daily_reporting",
    "weekly_reporting": "app.jobs.report_job.run_weekly_reporting",
    "negative_keyword_mining": "app.jobs.negative_keywords_job.run_negative_keyword_mining",
    "keyword_promotion": "app.jobs.keyword_promotion_job.run_keyword_promotion",
    "ml_bid_optimization": "app.jobs.ml_bid_job.run_ml_bid_optimization",
    "quality_score_monitor": "app.jobs.quality_score_job.run_quality_score_monitor",
}


@router.get("/", response_class=HTMLResponse)
async def job_history(request: Request, db: Session = Depends(get_db)):
    runs = db.query(JobRun).order_by(JobRun.started_at.desc()).limit(50).all()
    audit = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
    return templates.TemplateResponse(
        "jobs/history.html",
        {"request": request, "runs": runs, "audit_log": audit, "job_names": list(JOB_REGISTRY.keys())},
    )


@router.post("/trigger/{job_name}")
async def manual_trigger(job_name: str):
    if job_name not in JOB_REGISTRY:
        return JSONResponse({"error": f"Unknown job: {job_name}"}, status_code=400)

    module_path, func_name = JOB_REGISTRY[job_name].rsplit(".", 1)
    import importlib, threading
    try:
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name)
        threading.Thread(target=func, kwargs={"triggered_by": "manual_ui"}, daemon=True).start()
        return {"status": "started", "job": job_name}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/audit-log")
async def api_audit_log(page: int = 1, page_size: int = 50, db: Session = Depends(get_db)):
    offset = (page - 1) * page_size
    entries = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return [
        {
            "id": e.id,
            "entity_type": e.entity_type,
            "entity_resource": e.entity_resource,
            "action_taken": e.action_taken,
            "success": e.success,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in entries
    ]
