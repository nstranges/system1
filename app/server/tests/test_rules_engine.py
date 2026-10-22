import json
from pathlib import Path

import pytest

from system1.domain.policy import Rule
from system1.domain.rules_engine import evaluate, is_fully_testable, thresholds

RULES_PATH = Path(__file__).parents[1] / "src/system1/templates/data/tallyfern/rules.json"
FACTS_PATH = Path(__file__).parents[3] / "data/raw/facts.jsonl"


def tallyfern_rules() -> list[Rule]:
    return [Rule.model_validate(r) for r in json.loads(RULES_PATH.read_text())]


@pytest.mark.skipif(not FACTS_PATH.exists(), reason="phase 1 facts file missing")
def test_tallyfern_rules_match_phase1_router():
    rules = tallyfern_rules()
    records = [json.loads(line) for line in FACTS_PATH.read_text().splitlines() if line.strip()]
    assert len(records) > 0
    for record in records:
        match = evaluate(rules, record["facts"])
        assert match is not None
        assert (match.label, match.rule_id) == (record["queue"], record["rule_id"]), record["id"]


def test_unknown_fact_never_meets_condition():
    facts = {"issue_type": "refund_request", "secondary_issue": None, "amount_usd": None, "days_since_charge": None}
    match = evaluate(tallyfern_rules(), facts)
    assert (match.label, match.rule_id) == ("billing_refunds", "R05")


def test_testability_and_thresholds():
    rules = tallyfern_rules()
    assert is_fully_testable(rules)
    assert not is_fully_testable([Rule(id="a", text="t", label="x"), Rule(id="b", text="t", label="y")])
    assert 500 in thresholds(rules)["amount_usd"]
