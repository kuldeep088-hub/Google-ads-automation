import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import AutomationRule

logger = logging.getLogger(__name__)
router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

RULE_TYPES = [
    "cpa_bid", "tod_bid", "device_bid", "keyword_performance_bid",
    "budget_cap", "budget_redistribute", "budget_pause",
]


@router.get("/", response_class=HTMLResponse)
async def list_rules(request: Request, db: Session = Depends(get_db)):
    rules = db.query(AutomationRule).order_by(AutomationRule.priority, AutomationRule.name).all()
    return templates.TemplateResponse(
        "rules/list.html", {"request": request, "rules": rules, "rule_types": RULE_TYPES}
    )


@router.get("/new", response_class=HTMLResponse)
async def new_rule_form(request: Request):
    return templates.TemplateResponse(
        "rules/form.html",
        {"request": request, "rule": None, "rule_types": RULE_TYPES, "action": "/rules/"},
    )


@router.post("/", response_class=HTMLResponse)
async def create_rule(
    request: Request,
    name: str = Form(...),
    rule_type: str = Form(...),
    scope: str = Form("account"),
    scope_id: str = Form(""),
    conditions_json: str = Form("[]"),
    action_json: str = Form("{}"),
    priority: int = Form(10),
    is_active: bool = Form(True),
    db: Session = Depends(get_db),
):
    try:
        json.loads(conditions_json)
        json.loads(action_json)
    except json.JSONDecodeError as e:
        return templates.TemplateResponse(
            "rules/form.html",
            {
                "request": request, "rule": None, "rule_types": RULE_TYPES,
                "action": "/rules/", "error": f"Invalid JSON: {e}",
                "form_data": {"name": name, "rule_type": rule_type},
            },
        )

    rule = AutomationRule(
        name=name,
        rule_type=rule_type,
        scope=scope,
        scope_id=scope_id or None,
        conditions=conditions_json,
        action=action_json,
        priority=priority,
        is_active=is_active,
    )
    db.add(rule)
    db.commit()
    return RedirectResponse(url="/rules/", status_code=303)


@router.get("/{rule_id}/edit", response_class=HTMLResponse)
async def edit_rule_form(rule_id: int, request: Request, db: Session = Depends(get_db)):
    rule = db.query(AutomationRule).get(rule_id)
    if not rule:
        return RedirectResponse(url="/rules/", status_code=303)
    return templates.TemplateResponse(
        "rules/form.html",
        {"request": request, "rule": rule, "rule_types": RULE_TYPES, "action": f"/rules/{rule_id}"},
    )


@router.post("/{rule_id}", response_class=HTMLResponse)
async def update_rule(
    rule_id: int,
    request: Request,
    name: str = Form(...),
    rule_type: str = Form(...),
    scope: str = Form("account"),
    scope_id: str = Form(""),
    conditions_json: str = Form("[]"),
    action_json: str = Form("{}"),
    priority: int = Form(10),
    is_active: bool = Form(True),
    db: Session = Depends(get_db),
):
    rule = db.query(AutomationRule).get(rule_id)
    if rule:
        rule.name = name
        rule.rule_type = rule_type
        rule.scope = scope
        rule.scope_id = scope_id or None
        rule.conditions = conditions_json
        rule.action = action_json
        rule.priority = priority
        rule.is_active = is_active
        rule.updated_at = datetime.utcnow()
        db.commit()
    return RedirectResponse(url="/rules/", status_code=303)


@router.post("/{rule_id}/toggle")
async def toggle_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(AutomationRule).get(rule_id)
    if rule:
        rule.is_active = not rule.is_active
        db.commit()
        return {"id": rule_id, "is_active": rule.is_active}
    return JSONResponse({"error": "not found"}, status_code=404)


@router.delete("/{rule_id}")
async def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(AutomationRule).get(rule_id)
    if rule:
        db.delete(rule)
        db.commit()
        return {"deleted": rule_id}
    return JSONResponse({"error": "not found"}, status_code=404)


@router.get("/api/list")
async def api_list_rules(db: Session = Depends(get_db)):
    rules = db.query(AutomationRule).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "rule_type": r.rule_type,
            "is_active": r.is_active,
            "scope": r.scope,
            "priority": r.priority,
            "conditions": json.loads(r.conditions),
            "action": json.loads(r.action),
        }
        for r in rules
    ]
