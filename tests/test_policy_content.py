"""Checks that the policy documents and question text agree with each other."""
import json
from pathlib import Path

# Laya's input window hasn't been measured yet (plan Task 3), so terse text uses the 512-token cap
TERSE_MAX_WORDS = 6

QUEUES = ["trust_safety", "incident_response", "billing_disputes", "finance_review", "billing_refunds",
          "payments_ops", "legacy_api", "api_support", "enterprise_identity", "account_access",
          "privacy_legal", "sales", "general_support"]

FACT_FIELDS = ["plan_tier", "region", "seats", "sso_enabled", "issue_type", "secondary_issue",
               "amount_usd", "days_since_charge", "api_version"]

def load():
    """Read questions.json."""
    return json.loads(Path("data/policy/questions.json").read_text())

def test_questions_json_has_canonical_queues_in_order():
    assert list(load()["queues"]) == QUEUES

def test_every_queue_has_terse_and_policy_text():
    for key, entry in load()["queues"].items():
        assert entry["name"] and entry["terse"], key
        assert 1 <= len(entry["terse"].split()) <= TERSE_MAX_WORDS, key
        assert entry["policy"]["covers"] and "excludes" in entry["policy"], key

def test_policy_md_defines_every_rule_and_queue():
    text = Path("data/policy/policy.md").read_text()
    for rule in [f"R{i:02d}" for i in range(1, 14)]:
        assert rule in text
    for key in QUEUES:
        assert key in text

def test_facts_schema_documents_every_field():
    text = Path("data/readback/facts_schema.md").read_text()
    for field in FACT_FIELDS:
        assert f"`{field}`" in text
