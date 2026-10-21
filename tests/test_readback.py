"""Tests for the blind read-back check."""
import json

from readback import compare, extracted_facts, write_blind

FIELDS = ["plan_tier", "region", "seats", "sso_enabled", "issue_type", "secondary_issue",
          "amount_usd", "days_since_charge", "api_version"]

def record(rid = "t0001", **facts):
    """A facts record routed by the real rules (defaults: a v1 API error -> legacy_api, P3)."""
    base = {"plan_tier": "pro", "region": "us", "seats": 10, "sso_enabled": False,
            "issue_type": "api_error", "secondary_issue": None, "amount_usd": None,
            "days_since_charge": None, "api_version": "v1"}
    base.update(facts)
    from policy import route
    d = route(base)
    return {"id": rid, "created_at": "2026-09-01", "facts": base, "queue": d.queue,
            "priority": d.priority, "rule_id": d.rule_id, "difficulty": "clear", "confusable_with": None,
            "style": {"tone": "calm", "length": "short", "typos": False, "implied_facts": False, "distractor": False}}

def extraction(rec, overrides = None, flags = None):
    """An agent extraction that copies the intended facts exactly, with per-field overrides."""
    overrides = overrides or {}
    facts = {}
    for field in FIELDS:
        value = rec["facts"][field]
        entry = {"value": value, "basis": "stated" if value is not None else "not_stated", "evidence": ""}
        entry.update(overrides.get(field, {}))
        facts[field] = entry
    base_flags = {"names_routing": False, "multiple_issues": False, "unrealistic": False, "notes": ""}
    return {"id": rec["id"], "facts": facts, "flags": {**base_flags, **(flags or {})}}

def test_blind_file_has_only_id_and_state(tmp_path):
    rec = record()
    path = tmp_path / "blind.jsonl"
    n = write_blind([rec], [{"id": "t0001", "subject": "v1 errors", "body": "Our v1 calls fail."}], path)
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    assert n == 1 and set(rows[0]) == {"id", "state"}
    assert rows[0]["state"]["ticket"]["body"] == "Our v1 calls fail."
    assert "queue" not in json.dumps(rows[0]) and "rule_id" not in json.dumps(rows[0])

def test_blind_only_ids(tmp_path):
    recs = [record("t0001"), record("t0002")]
    tickets = [{"id": r["id"], "subject": "s s s", "body": "b"} for r in recs]
    assert write_blind(recs, tickets, tmp_path / "b.jsonl", only_ids = {"t0002"}) == 1

def test_extracted_facts_casts_and_nulls():
    rec = record(issue_type = "refund_request", api_version = None, amount_usd = 640, days_since_charge = 5)
    entry = extraction(rec, {"amount_usd": {"value": "$640"}, "days_since_charge": {"value": "5"},
                             "seats": {"value": "10"}, "sso_enabled": {"value": "false"},
                             "region": {"value": "us", "basis": "conflicting"}})
    facts = extracted_facts(entry)
    assert facts["amount_usd"] == 640.0 and facts["days_since_charge"] == 5 and facts["seats"] == 10
    assert facts["sso_enabled"] is False and facts["region"] is None

def test_exact_extraction_passes():
    rec = record()
    report = compare([rec], {"t0001": extraction(rec)})
    assert report["ok_ids"] == ["t0001"] and report["failed"] == []

def test_implied_basis_counts_as_match():
    rec = record()
    report = compare([rec], {"t0001": extraction(rec, {"api_version": {"basis": "implied"}})})
    assert report["ok_ids"] == ["t0001"]

def test_missing_decisive_fact_fails():
    rec = record()
    entry = extraction(rec, {"api_version": {"value": None, "basis": "not_stated"}})
    report = compare([rec], {"t0001": entry})
    assert report["ok_ids"] == []
    assert "queue legacy_api != api_support" in report["failed"][0]["reasons"]

def test_priority_mismatch_fails():
    rec = record(issue_type = "failed_payout", api_version = None, amount_usd = 10000)
    entry = extraction(rec, {"amount_usd": {"value": 9000}})
    report = compare([rec], {"t0001": entry})
    assert "priority P2 != P3" in report["failed"][0]["reasons"]

def test_names_routing_fails():
    rec = record()
    report = compare([rec], {"t0001": extraction(rec, flags = {"names_routing": True})})
    assert report["failed"][0]["reasons"] == ["names_routing"]

def test_conflicting_on_set_field_fails():
    rec = record(issue_type = "refund_request", api_version = None, amount_usd = 100, days_since_charge = 3)
    entry = extraction(rec, {"days_since_charge": {"value": None, "basis": "conflicting"}})
    report = compare([rec], {"t0001": entry})
    assert any("conflicting: days_since_charge" in r for r in report["failed"][0]["reasons"])

def test_invalid_extraction_fails():
    rec = record()
    entry = extraction(rec, {"issue_type": {"value": "something_else"}})
    report = compare([rec], {"t0001": entry})
    assert report["failed"][0]["reasons"][0].startswith("invalid extraction")

def test_missing_ticket_listed():
    report = compare([record("t0001"), record("t0002")], {"t0001": extraction(record("t0001"))})
    assert report["missing"] == ["t0002"] and report["total"] == 2

def test_unrealistic_listed_but_passes():
    rec = record()
    report = compare([rec], {"t0001": extraction(rec, flags = {"unrealistic": True})})
    assert report["ok_ids"] == ["t0001"] and report["unrealistic"] == ["t0001"]

def test_later_file_overrides_earlier(tmp_path):
    from readback import load_extractions
    rec = record()
    bad = extraction(rec, {"api_version": {"value": None, "basis": "not_stated"}})
    good = extraction(rec)
    (tmp_path / "a.jsonl").write_text(json.dumps(bad) + "\n")
    (tmp_path / "b.jsonl").write_text(json.dumps(good) + "\n")
    merged = load_extractions([tmp_path / "a.jsonl", tmp_path / "b.jsonl"])
    assert compare([rec], merged)["ok_ids"] == ["t0001"]
