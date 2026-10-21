"""Tests for the seeded facts grid that decides every ticket before it is written."""
from collections import Counter

from facts_grid import LENGTH_BUCKETS, build_grid
from policy import QUEUES, route

GRID = build_grid(550, 20261020)

def test_labels_match_rules():
    for r in GRID:
        assert tuple(route(r["facts"])) == (r["queue"], r["priority"], r["rule_id"]), r["id"]

def test_queue_balance():
    counts = Counter(r["queue"] for r in GRID)
    assert set(counts) == set(QUEUES) and set(counts.values()) <= {42, 43}

def test_difficulty_mix_per_queue():
    for q in QUEUES:
        k = sum(r["queue"] == q for r in GRID)
        mix = Counter(r["difficulty"] for r in GRID if r["queue"] == q)
        assert mix["clear"] == round(0.5 * k) and mix["borderline"] == round(0.3 * k), q
        assert mix["tricky"] == k - mix["clear"] - mix["borderline"], q

def test_borderline_numbers_in_window():
    for r in GRID:
        f, rule = r["facts"], r["rule_id"]
        if r["difficulty"] != "borderline" or rule not in {"R04", "R05", "R06", "R12"}:
            continue
        assert any([
            rule in {"R04", "R05"} and f["amount_usd"] is not None and 450 <= f["amount_usd"] <= 550,
            rule in {"R04", "R05"} and f["days_since_charge"] is not None and 27 <= f["days_since_charge"] <= 33,
            rule == "R06" and 9000 <= f["amount_usd"] <= 11000,
            rule == "R12" and 45 <= f["seats"] <= 55,
        ]), r["id"]

def test_borderline_without_threshold_has_confusable_queue():
    for r in GRID:
        if r["difficulty"] == "borderline" and r["rule_id"] not in {"R04", "R05", "R06", "R12"}:
            assert r["confusable_with"] in QUEUES and r["confusable_with"] != r["queue"], r["id"]

def test_tricky_half_have_secondary_issue():
    for q in QUEUES:
        tricky = [r for r in GRID if r["queue"] == q and r["difficulty"] == "tricky"]
        with_secondary = [r for r in tricky if r["facts"]["secondary_issue"]]
        assert len(with_secondary) == len(tricky) // 2, q
        assert all(r["facts"]["secondary_issue"] != r["facts"]["issue_type"] for r in with_secondary)
        assert all(r["style"]["implied_facts"] for r in tricky if not r["facts"]["secondary_issue"])

def test_override_queues_use_secondary_override():
    overrides = {"trust_safety": "security_concern", "incident_response": "outage_report",
                 "billing_disputes": "chargeback_dispute"}
    for r in GRID:
        if r["queue"] in overrides and r["facts"]["secondary_issue"]:
            assert r["facts"]["secondary_issue"] == overrides[r["queue"]], r["id"]

def test_sso_only_on_enterprise():
    assert all(r["facts"]["plan_tier"] == "enterprise" for r in build_grid(550, 1) if r["facts"]["sso_enabled"])

def test_deterministic():
    assert build_grid(550, 7) == build_grid(550, 7) and build_grid(550, 7) != build_grid(550, 8)

def test_unique_ids_and_valid_lengths():
    assert len({r["id"] for r in GRID}) == 550
    assert all(r["style"]["length"] in LENGTH_BUCKETS for r in GRID)

def test_created_at_in_range():
    assert all("2026-08-01" <= r["created_at"] <= "2026-10-15" for r in GRID)

def test_id_start_offsets_ids():
    assert build_grid(13, 1, id_start = 551)[0]["id"] == "t0551"
