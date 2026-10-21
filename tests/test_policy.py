"""Rule-by-rule and boundary tests for the triage rules engine."""
import json
from pathlib import Path

import pytest

from policy import QUEUES, load_questions, route

def facts(**overrides):
    """A valid facts record, with overrides applied."""
    base = {
        "plan_tier": "pro", "region": "us", "seats": 10, "sso_enabled": False,
        "issue_type": "how_to", "secondary_issue": None, "amount_usd": None,
        "days_since_charge": None, "api_version": None,
    }
    return {**base, **overrides}

@pytest.mark.parametrize("overrides, expected", [
    ({"issue_type": "security_concern"}, ("trust_safety", "P1", "R01")),
    ({"issue_type": "login_problem", "secondary_issue": "security_concern"}, ("trust_safety", "P1", "R01")),
    ({"issue_type": "outage_report", "plan_tier": "enterprise", "seats": 300}, ("incident_response", "P1", "R02")),
    ({"issue_type": "outage_report"}, ("incident_response", "P2", "R02")),
    ({"issue_type": "refund_request", "secondary_issue": "chargeback_dispute"}, ("billing_disputes", "P3", "R03")),
    ({"issue_type": "refund_request", "amount_usd": 500, "days_since_charge": 30}, ("billing_refunds", "P3", "R05")),
    ({"issue_type": "refund_request", "amount_usd": 500.01, "days_since_charge": 3}, ("finance_review", "P3", "R04")),
    ({"issue_type": "refund_request", "amount_usd": 100, "days_since_charge": 31}, ("finance_review", "P3", "R04")),
    ({"issue_type": "refund_request"}, ("billing_refunds", "P3", "R05")),
    ({"issue_type": "failed_payout", "amount_usd": 10000}, ("payments_ops", "P2", "R06")),
    ({"issue_type": "failed_payout", "amount_usd": 9999}, ("payments_ops", "P3", "R06")),
    ({"issue_type": "api_error", "api_version": "v1"}, ("legacy_api", "P3", "R07")),
    ({"issue_type": "api_error", "api_version": "v2"}, ("api_support", "P3", "R08")),
    ({"issue_type": "api_error"}, ("api_support", "P3", "R08")),
    ({"issue_type": "login_problem", "plan_tier": "enterprise", "seats": 200, "sso_enabled": True}, ("enterprise_identity", "P2", "R09")),
    ({"issue_type": "login_problem", "plan_tier": "enterprise", "seats": 200}, ("account_access", "P3", "R10")),
    ({"issue_type": "data_request", "region": "eu"}, ("privacy_legal", "P3", "R11")),
    ({"issue_type": "data_request", "region": "us"}, ("general_support", "P4", "R13")),
    ({"issue_type": "plan_change", "seats": 50}, ("sales", "P4", "R12")),
    ({"issue_type": "plan_change", "seats": 49}, ("general_support", "P4", "R13")),
    ({"issue_type": "plan_change", "plan_tier": "enterprise", "seats": 60}, ("sales", "P4", "R12")),
    ({"issue_type": "billing_question"}, ("general_support", "P4", "R13")),
])
def test_route(overrides, expected):
    assert tuple(route(facts(**overrides))) == expected

def test_unknown_issue_type_raises():
    with pytest.raises(ValueError, match = "issue_type"):
        route(facts(issue_type = "bogus"))

def test_missing_field_raises():
    record = facts()
    del record["region"]
    with pytest.raises(ValueError, match = "region"):
        route(record)

def test_sso_requires_enterprise():
    with pytest.raises(ValueError, match = "sso_enabled"):
        route(facts(sso_enabled = True))

def test_queues_match_questions_json():
    assert QUEUES == list(json.loads(Path("data/policy/questions.json").read_text())["queues"])

def test_load_questions_respects_order():
    order = list(reversed(QUEUES))
    assert list(load_questions("terse", order = order)["queue"]["criteria"]) == order

def test_policy_variant_carries_rules():
    assert "covers" in load_questions("policy")["queue"]["criteria"]["finance_review"]
