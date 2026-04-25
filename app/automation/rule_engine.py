import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AutomationRule, AuditLog, JobRun
from app.google_ads.bid_service import BidService
from app.google_ads.budget_service import BudgetService

logger = logging.getLogger(__name__)

MICROS = 1_000_000


@dataclass
class PerformanceContext:
    keyword_rows: list[dict] = field(default_factory=list)
    device_rows: list[dict] = field(default_factory=list)
    hourly_rows: list[dict] = field(default_factory=list)
    budget_rows: list[dict] = field(default_factory=list)
    current_hour: int = 0
    current_day_of_week: int = 0


@dataclass
class ActionResult:
    success: bool
    entity_resource: str
    entity_type: str
    action_taken: str
    old_value: dict = field(default_factory=dict)
    new_value: dict = field(default_factory=dict)
    error_message: str = ""


@dataclass
class EngineResult:
    rules_evaluated: int = 0
    actions_taken: int = 0
    errors_count: int = 0
    action_results: list[ActionResult] = field(default_factory=list)

    def __iadd__(self, other: "EngineResult") -> "EngineResult":
        self.rules_evaluated += other.rules_evaluated
        self.actions_taken += other.actions_taken
        self.errors_count += other.errors_count
        self.action_results.extend(other.action_results)
        return self


class RuleEngine:
    def __init__(self, db: Session, customer_id: str | None = None):
        self.db = db
        self.customer_id = customer_id or settings.GOOGLE_ADS_TARGET_CUSTOMER_ID
        self.bid_service = BidService(self.customer_id)
        self.budget_service = BudgetService(self.customer_id)

    def run(self, rule_type: str) -> EngineResult:
        rules = self._load_active_rules(rule_type)
        if not rules:
            return EngineResult()

        context = self._build_context(rule_type)
        result = EngineResult()

        for rule in sorted(rules, key=lambda r: r.priority):
            conditions = json.loads(rule.conditions)
            action = json.loads(rule.action)
            targets = self._get_targets(rule, context)

            for target in targets:
                result.rules_evaluated += 1
                if self._evaluate_conditions(conditions, target, context):
                    ar = self._execute_action(rule, action, target)
                    result.action_results.append(ar)
                    if ar.success:
                        result.actions_taken += 1
                    else:
                        result.errors_count += 1
                    self._write_audit(rule, ar)

        return result

    def _load_active_rules(self, rule_type: str) -> list[AutomationRule]:
        return (
            self.db.query(AutomationRule)
            .filter(AutomationRule.rule_type == rule_type, AutomationRule.is_active == True)
            .all()
        )

    def _build_context(self, rule_type: str) -> PerformanceContext:
        now = datetime.utcnow()
        ctx = PerformanceContext(
            current_hour=now.hour,
            current_day_of_week=now.weekday(),
        )
        if rule_type in ("cpa_bid", "keyword_performance_bid"):
            ctx.keyword_rows = self.bid_service.get_keyword_performance("LAST_7_DAYS")
        if rule_type == "device_bid":
            ctx.device_rows = self.bid_service.get_device_performance("LAST_7_DAYS")
        if rule_type == "tod_bid":
            ctx.hourly_rows = self.bid_service.get_hourly_performance()
        if rule_type in ("budget_cap", "budget_redistribute", "budget_pause"):
            ctx.budget_rows = self.budget_service.get_all_campaign_budgets()
        return ctx

    def _get_targets(self, rule: AutomationRule, ctx: PerformanceContext) -> list[dict]:
        if rule.rule_type in ("cpa_bid", "keyword_performance_bid"):
            rows = ctx.keyword_rows
        elif rule.rule_type == "device_bid":
            rows = ctx.device_rows
        elif rule.rule_type == "tod_bid":
            rows = ctx.keyword_rows or ctx.hourly_rows
        elif rule.rule_type in ("budget_cap", "budget_redistribute", "budget_pause"):
            rows = ctx.budget_rows
        else:
            rows = ctx.keyword_rows

        if rule.scope == "campaign" and rule.scope_id:
            return [r for r in rows if r.get("campaign_resource_name") == rule.scope_id]
        if rule.scope == "keyword" and rule.scope_id:
            return [r for r in rows if r.get("criterion_resource_name") == rule.scope_id]
        return rows

    def _evaluate_conditions(
        self, conditions: list[dict], target: dict, ctx: PerformanceContext
    ) -> bool:
        for cond in conditions:
            val = self._resolve_metric(cond["metric"], target, ctx)
            if not self._compare(val, cond["operator"], cond["value"]):
                return False
        return True

    def _resolve_metric(self, metric: str, target: dict, ctx: PerformanceContext):
        if metric == "hour_of_day":
            return ctx.current_hour
        if metric == "day_of_week":
            return ctx.current_day_of_week
        if metric == "device":
            return target.get("device", "")
        if metric == "cpa":
            cost = target.get("cost_micros", 0)
            conv = target.get("conversions", 0)
            return (cost / MICROS) / max(conv, 0.001) if conv > 0 else 9999
        if metric == "cpa_micros":
            return target.get("cpa_micros", 0)
        if metric == "roas":
            cost = target.get("cost_micros", 0)
            conv_val = target.get("conversions_value", 0)
            return conv_val / max(cost / MICROS, 0.001)
        return target.get(metric, 0)

    def _compare(self, actual, operator: str, threshold) -> bool:
        try:
            if operator == "gt":
                return actual > threshold
            if operator == "lt":
                return actual < threshold
            if operator == "gte":
                return actual >= threshold
            if operator == "lte":
                return actual <= threshold
            if operator == "eq":
                return str(actual).upper() == str(threshold).upper()
            if operator == "between":
                low, high = threshold
                return low <= actual <= high
        except Exception:
            pass
        return False

    def _execute_action(
        self, rule: AutomationRule, action: dict, target: dict
    ) -> ActionResult:
        action_type = action.get("type", "")
        entity_type = "keyword" if "criterion_resource_name" in target else "campaign"
        entity_resource = target.get(
            "criterion_resource_name", target.get("campaign_resource_name", "")
        )

        try:
            if action_type == "adjust_bid_percent":
                return self._adjust_bid_percent(target, action, entity_resource)
            if action_type == "set_bid_adjustment":
                return self._set_bid_adjustment(target, action, entity_resource)
            if action_type == "pause_entity":
                return self._pause_entity(target, entity_resource, entity_type)
            if action_type == "enable_entity":
                return self._enable_entity(target, entity_resource, entity_type)
            if action_type == "adjust_budget_percent":
                return self._adjust_budget_percent(target, action, entity_resource)
            if action_type == "set_budget_micros":
                return self._set_budget_micros(target, action, entity_resource)
            return ActionResult(
                success=False,
                entity_resource=entity_resource,
                entity_type=entity_type,
                action_taken=f"unknown action type: {action_type}",
                error_message=f"Unknown action type: {action_type}",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                entity_resource=entity_resource,
                entity_type=entity_type,
                action_taken=action_type,
                error_message=str(e),
            )

    def _adjust_bid_percent(self, target: dict, action: dict, entity_resource: str) -> ActionResult:
        current = target.get("cpc_bid_micros", 0)
        delta = action["value"] / 100.0
        new_bid = int(current * (1 + delta))
        new_bid = max(action.get("min_bid_micros", 10_000), new_bid)
        new_bid = min(action.get("max_bid_micros", 100_000_000), new_bid)
        success = self.bid_service.update_keyword_bid(entity_resource, new_bid)
        return ActionResult(
            success=success,
            entity_resource=entity_resource,
            entity_type="keyword",
            action_taken=f"adjust_bid {action['value']:+.1f}%: {current} → {new_bid} micros",
            old_value={"cpc_bid_micros": current},
            new_value={"cpc_bid_micros": new_bid},
        )

    def _set_bid_adjustment(self, target: dict, action: dict, entity_resource: str) -> ActionResult:
        device = target.get("device", "MOBILE")
        campaign_resource = target.get("campaign_resource_name", entity_resource)
        adjustment = action["value"]
        success = self.bid_service.update_campaign_bid_adjustment(campaign_resource, device, adjustment)
        return ActionResult(
            success=success,
            entity_resource=campaign_resource,
            entity_type="campaign",
            action_taken=f"set_bid_adjustment device={device} → {adjustment}",
            new_value={"bid_modifier": adjustment, "device": device},
        )

    def _pause_entity(self, target: dict, entity_resource: str, entity_type: str) -> ActionResult:
        campaign_resource = target.get("campaign_resource_name", entity_resource)
        success = self.budget_service.pause_campaign(campaign_resource)
        return ActionResult(
            success=success,
            entity_resource=campaign_resource,
            entity_type=entity_type,
            action_taken="pause_campaign",
            old_value={"status": "ENABLED"},
            new_value={"status": "PAUSED"},
        )

    def _enable_entity(self, target: dict, entity_resource: str, entity_type: str) -> ActionResult:
        campaign_resource = target.get("campaign_resource_name", entity_resource)
        success = self.budget_service.enable_campaign(campaign_resource)
        return ActionResult(
            success=success,
            entity_resource=campaign_resource,
            entity_type=entity_type,
            action_taken="enable_campaign",
            old_value={"status": "PAUSED"},
            new_value={"status": "ENABLED"},
        )

    def _adjust_budget_percent(self, target: dict, action: dict, entity_resource: str) -> ActionResult:
        current = target.get("daily_budget_micros", 0)
        delta = action["value"] / 100.0
        new_budget = int(current * (1 + delta))
        new_budget = max(action.get("min_budget_micros", 100_000), new_budget)
        budget_resource = target.get("budget_resource_name", "")
        success = self.budget_service.update_budget(budget_resource, new_budget)
        return ActionResult(
            success=success,
            entity_resource=entity_resource,
            entity_type="campaign",
            action_taken=f"adjust_budget {action['value']:+.1f}%: {current} → {new_budget} micros",
            old_value={"daily_budget_micros": current},
            new_value={"daily_budget_micros": new_budget},
        )

    def _set_budget_micros(self, target: dict, action: dict, entity_resource: str) -> ActionResult:
        new_budget = action["value"]
        budget_resource = target.get("budget_resource_name", "")
        success = self.budget_service.update_budget(budget_resource, new_budget)
        return ActionResult(
            success=success,
            entity_resource=entity_resource,
            entity_type="campaign",
            action_taken=f"set_budget → {new_budget} micros",
            new_value={"daily_budget_micros": new_budget},
        )

    def _write_audit(self, rule: AutomationRule, ar: ActionResult) -> None:
        try:
            entry = AuditLog(
                rule_id=rule.id,
                entity_type=ar.entity_type,
                entity_resource=ar.entity_resource,
                action_taken=ar.action_taken,
                old_value=json.dumps(ar.old_value) if ar.old_value else None,
                new_value=json.dumps(ar.new_value) if ar.new_value else None,
                success=ar.success,
                error_message=ar.error_message or None,
            )
            self.db.add(entry)
            self.db.commit()
        except Exception as e:
            logger.error("Failed to write audit log: %s", e)
