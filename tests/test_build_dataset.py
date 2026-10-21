"""Tests for deduplication, frozen stratified splits and parquet assembly."""
import hashlib
import json
from collections import Counter

import pandas as pd

from build_dataset import assemble_row, assign_splits, char_ngrams, dedupe, jaccard, main, option_order
from facts_grid import build_grid
from policy import QUEUES, route

def strata_for(n, n_strata = 39):
    """n ids spread round-robin over n_strata stratum keys."""
    return {f"t{i:04d}": f"s{i % n_strata:02d}" for i in range(1, n + 1)}

def test_jaccard_of_identical_text_is_one():
    a = char_ngrams("The payout of $2,300 never arrived in our account.")
    assert jaccard(a, a) == 1.0

def test_dedupe_drops_near_duplicate():
    body = "Our payout of $2,300 was due on Monday and still has not arrived in our bank account at all."
    kept, dropped = dedupe([("t0001", body), ("t0002", body.replace("Monday", "Tuesday"))])
    assert kept == ["t0001"] and dropped == ["t0002"]

def test_dedupe_keeps_unrelated_bodies():
    kept, dropped = dedupe([("t0001", "Please refund the add-on we bought by mistake last week."),
                            ("t0002", "Every call to the v1 invoices endpoint now returns a 500 error.")])
    assert dropped == []

def test_split_sizes_500():
    splits = assign_splits(strata_for(500), 20261020, {})
    assert Counter(splits.values()) == {"train": 300, "cal": 50, "test": 150}

def test_split_is_stratified():
    strata = strata_for(500)
    splits = assign_splits(strata, 20261020, {})
    for key in set(strata.values()):
        ids = [i for i, s in strata.items() if s == key]
        tests = sum(splits[i] == "test" for i in ids)
        assert abs(tests - 0.3 * len(ids)) <= 1, key

def test_frozen_assignments_never_change():
    first = assign_splits(strata_for(500), 20261020, {})
    grown = strata_for(600)
    second = assign_splits(grown, 20261020, frozen = first)
    assert all(second[i] == first[i] for i in first)
    assert set(second) == set(grown)

def test_option_order_deterministic_and_shared():
    order = option_order("t0007", 20261020)
    assert order == option_order("t0007", 20261020) and sorted(order) == sorted(QUEUES)
    assert order != option_order("t0008", 20261020)
    rec = build_grid(13, 1)[0]
    row = assemble_row(rec, {"id": rec["id"], "subject": "s s s", "body": "b"}, "train", order)
    assert list(json.loads(row["questions_terse"])["queue"]["criteria"]) == order
    assert list(json.loads(row["questions_policy"])["queue"]["criteria"]) == order
    assert json.loads(row["option_order"]) == order

def test_gold_matches_record_queue():
    rec = build_grid(13, 1)[0]
    row = assemble_row(rec, {"id": rec["id"], "subject": "s s s", "body": "b"}, "test", QUEUES)
    assert json.loads(row["gold"]) == {"queue": {"type": "choice", "label": route(rec["facts"]).queue}}
    assert row["gold_priority"] == rec["priority"] and row["split"] == "test"

def _fixture(tmp_path, n = 26, duplicate = None, ok_ids = None):
    """Write facts, tickets and a read-back report; returns the paths main() needs."""
    records = build_grid(n, 3)
    tickets = [{"id": r["id"], "subject": "A ticket subject",
                "body": " ".join(hashlib.md5(f"{i}-{k}".encode()).hexdigest()[:8] for k in range(20))}
               for i, r in enumerate(records)]
    if duplicate:
        src, dst = duplicate
        body = next(t["body"] for t in tickets if t["id"] == src)
        next(t for t in tickets if t["id"] == dst)["body"] = body
    paths = {name: tmp_path / f"{name}.jsonl" for name in ("facts", "tickets")}
    paths["facts"].write_text("".join(json.dumps(r) + "\n" for r in records))
    paths["tickets"].write_text("".join(json.dumps(t) + "\n" for t in tickets))
    paths["report"] = tmp_path / "report.json"
    paths["report"].write_text(json.dumps({"ok_ids": ok_ids if ok_ids is not None else [r["id"] for r in records],
                                           "failed": [], "missing": []}))
    return paths

def _run(paths, out_dir, *extra):
    """Call main() on fixture paths."""
    main(["--facts", str(paths["facts"]), "--tickets", str(paths["tickets"]),
          "--readback-report", str(paths["report"]), "--out-dir", str(out_dir), *extra])

def test_dedupe_runs_before_split(tmp_path):
    paths = _fixture(tmp_path, duplicate = ("t0001", "t0002"))
    _run(paths, tmp_path / "build")
    df = pd.read_parquet(tmp_path / "build" / "triage.parquet")
    assert "t0001" in set(df["id"]) and "t0002" not in set(df["id"])
    assert "t0002" not in json.loads((tmp_path / "build" / "splits.json").read_text())

def test_only_readback_ok_ids_included(tmp_path):
    paths = _fixture(tmp_path, ok_ids = ["t0001", "t0003", "t0005"])
    _run(paths, tmp_path / "build")
    assert sorted(pd.read_parquet(tmp_path / "build" / "triage.parquet")["id"]) == ["t0001", "t0003", "t0005"]

def test_parquet_columns(tmp_path):
    _run(_fixture(tmp_path), tmp_path / "build")
    df = pd.read_parquet(tmp_path / "build" / "triage.parquet")
    assert list(df.columns) == ["id", "split", "difficulty", "rule_id", "queue", "priority", "facts", "state",
                                "questions_terse", "questions_policy", "gold", "gold_priority", "option_order"]

def test_rebuild_reuses_frozen_splits(tmp_path):
    paths = _fixture(tmp_path)
    _run(paths, tmp_path / "build")
    first = json.loads((tmp_path / "build" / "splits.json").read_text())
    _run(paths, tmp_path / "build", "--seed", "999")
    assert json.loads((tmp_path / "build" / "splits.json").read_text()) == first

def test_provisional_skips_readback_and_splits_file(tmp_path):
    paths = _fixture(tmp_path, ok_ids = [])
    _run(paths, tmp_path / "build", "--provisional")
    df = pd.read_parquet(tmp_path / "build" / "triage_provisional.parquet")
    assert len(df) == 26
    assert not (tmp_path / "build" / "splits.json").exists()
    assert not (tmp_path / "build" / "triage.parquet").exists()
