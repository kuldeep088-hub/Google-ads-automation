import json
from unittest.mock import MagicMock, patch

import pytest

from app.automation.rule_engine import PerformanceContext, RuleEngine
from app.db.models import AutomationRule


def _make_rule(db, rule_type, conditions, action, is_active=True):
    rule = AutomationRule(
        name="test rule",
        rule_type=rule_type,
        scope="account",
        conditions=json.dumps(conditions),
        action=json.dumps(action),
        priority=10,
        is_active=is_active,
    )
    db.add(rule)
    db.commit()
    return rule


@patch("app.automation.rule_engine.BidService")
@patch("app.automation.rule_engine.BudgetService")
def test_cpa_rule_triggers_bid_decrease(mock_budget, mock_bid, db_session):
    mock_bid_instance = MagicMock()
    mock_bid.return_value = mock_bid_instance
    mock_bid_instance.get_keyword_performance.return_value = [
        {
            "criterion_resource_name": "customers/1/adGroupCriteria/1",
            "cpc_bid_micros": 1_000_000,
            "cost_micros": 300_000_000,
            "conversions": 10.0,
            "clicks": 100,
            "campaign_resource_name": "customers/1/campaigns/1",
        }
    ]
    mock_bid_instance.update_keyword_bid.return_value = True

    _make_rule(
        db_session,
        "cpa_bid",
        [{"metric": "cpa", "operator": "gt", "value": 25.0}],
        {"type": "adjust_bid_percent", "value": -10, "min_bid_micros": 100_000},
    )

    engine = RuleEngine(db=db_session, customer_id="123")
    result = engine.run("cpa_bid")

    assert result.actions_taken == 1
    mock_bid_instance.update_keyword_bid.assert_called_once()
    call_args = mock_bid_instance.update_keyword_bid.call_args
    new_bid = call_args[0][1]
    assert new_bid == 900_000


@patch("app.automation.rule_engine.BidService")
@patch("app.automation.rule_engine.BudgetService")
def test_inactive_rule_not_evaluated(mock_budget, mock_bid, db_session):
    mock_bid_instance = MagicMock()
    mock_bid.return_value = mock_bid_instance
    mock_bid_instance.get_keyword_performance.return_value = [
        {"criterion_resource_name": "x", "cpc_bid_micros": 500_000, "cost_micros": 100_000_000, "conversions": 1.0, "clicks": 50, "campaign_resource_name": "c/1"}
    ]

    _make_rule(
        db_session,
        "cpa_bid",
        [{"metric": "cpa", "operator": "gt", "value": 5.0}],
        {"type": "adjust_bid_percent", "value": -5},
        is_active=False,
    )

    engine = RuleEngine(db=db_session, customer_id="123")
    result = engine.run("cpa_bid")
    assert result.actions_taken == 0


def test_compare_operators():
    engine = RuleEngine.__new__(RuleEngine)
    assert engine._compare(30, "gt", 25) is True
    assert engine._compare(10, "gt", 25) is False
    assert engine._compare(25, "gte", 25) is True
    assert engine._compare(10, "between", [5, 15]) is True
    assert engine._compare(20, "between", [5, 15]) is False
    assert engine._compare("MOBILE", "eq", "mobile") is True
