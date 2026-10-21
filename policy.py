"""Tallyfern triage rules: turn a ticket's facts into its gold queue and priority.

This mirrors data/policy/policy.md rule for rule. If you change one, change the other.
"""
import json
from pathlib import Path
from typing import NamedTuple

QUESTIONS_PATH = Path("data/policy/questions.json")
SEED = 20261020

REFUND_AMOUNT_LIMIT = 500
REFUND_WINDOW_DAYS = 30
PAYOUT_P2_AMOUNT = 10000
SALES_SEATS = 50

ISSUE_TYPES = ("refund_request", "chargeback_dispute", "billing_question", "failed_payout", "login_problem",
               "api_error", "data_request", "outage_report", "security_concern", "plan_change", "how_to")

# Allowed values per field. Text-derived fields may also be None ("not stated").
FACT_FIELDS = {
    "plan_tier": ("free", "starter", "pro", "enterprise"),
    "region": ("us", "ca", "eu", "uk", "apac"),
    "seats": "int",
    "sso_enabled": "bool",
    "issue_type": ISSUE_TYPES,
    "secondary_issue": ISSUE_TYPES,
    "amount_usd": "float",
    "days_since_charge": "int",
    "api_version": ("v1", "v2"),
}
NULLABLE = {"secondary_issue", "amount_usd", "days_since_charge", "api_version"}

QUEUES = list(json.loads(QUESTIONS_PATH.read_text())["queues"])
PRIORITIES = ["P1", "P2", "P3", "P4"]

class Decision(NamedTuple):
    queue: str
    priority: str
    rule_id: str

def _valid_value(kind, value):
    """Check one value against its FACT_FIELDS entry."""
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    if kind == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
    if kind == "bool":
        return isinstance(value, bool)
    return value in kind

def validate_facts(facts):
    """Raise ValueError naming the first missing, unknown or invalid field."""
    for field, kind in FACT_FIELDS.items():
        if field not in facts:
            raise ValueError(f"missing fact field: {field}")
        value = facts[field]
        if value is None and field in NULLABLE:
            continue
        if not _valid_value(kind, value):
            raise ValueError(f"invalid value for {field}: {value!r}")
    extra = set(facts) - set(FACT_FIELDS)
    if extra:
        raise ValueError(f"unknown fact fields: {sorted(extra)}")
    if facts["sso_enabled"] and facts["plan_tier"] != "enterprise":
        raise ValueError("sso_enabled is only allowed on enterprise accounts")

def _queue(facts):
    """Return (queue, rule_id) for the first routing rule that matches."""
    issue = facts["issue_type"]
    mentions = {issue, facts["secondary_issue"]}
    amount, days = facts["amount_usd"], facts["days_since_charge"]

    if "security_concern" in mentions:
        return "trust_safety", "R01"
    if "outage_report" in mentions:
        return "incident_response", "R02"
    if "chargeback_dispute" in mentions:
        return "billing_disputes", "R03"
    if issue == "refund_request":
        # Unknown amount or timing never meets a condition
        over_amount = amount is not None and amount > REFUND_AMOUNT_LIMIT
        too_late = days is not None and days > REFUND_WINDOW_DAYS
        return ("finance_review", "R04") if over_amount or too_late else ("billing_refunds", "R05")
    if issue == "failed_payout":
        return "payments_ops", "R06"
    if issue == "api_error":
        return ("legacy_api", "R07") if facts["api_version"] == "v1" else ("api_support", "R08")
    if issue == "login_problem":
        if facts["plan_tier"] == "enterprise" and facts["sso_enabled"]:
            return "enterprise_identity", "R09"
        return "account_access", "R10"
    if issue == "data_request" and facts["region"] in ("eu", "uk"):
        return "privacy_legal", "R11"
    if issue == "plan_change" and (facts["seats"] >= SALES_SEATS or facts["plan_tier"] == "enterprise"):
        return "sales", "R12"
    return "general_support", "R13"

def _priority(facts, rule_id):
    """Return the priority for a ticket routed by rule_id."""
    if rule_id == "R01":
        return "P1"
    if rule_id == "R02":
        return "P1" if facts["plan_tier"] == "enterprise" else "P2"
    if rule_id == "R06" and facts["amount_usd"] is not None and facts["amount_usd"] >= PAYOUT_P2_AMOUNT:
        return "P2"
    if rule_id == "R09":
        return "P2"
    if rule_id in ("R12", "R13"):
        return "P4"
    return "P3"

def route(facts):
    """Validate the facts, then return the gold Decision(queue, priority, rule_id)."""
    validate_facts(facts)
    queue, rule_id = _queue(facts)
    return Decision(queue, _priority(facts, rule_id), rule_id)

def load_questions(variant, order = None):
    """Build the Jev/Laya queue question for 'terse' or 'policy', with options in `order`."""
    spec = json.loads(QUESTIONS_PATH.read_text())
    order = order or QUEUES
    return {"queue": {
        "type": "choice",
        "instructions": spec["instructions"][variant],
        "criteria": {key: spec["queues"][key][variant] for key in order},
    }}
