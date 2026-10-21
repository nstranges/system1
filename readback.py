"""Blind read-back check: a separate agent extracts facts from ticket text alone, and we keep
only tickets whose extracted facts route to the same queue and priority as their intended facts.

    python readback.py blind                                 # -> data/readback/tickets_blind.jsonl
    python readback.py blind --only-failed data/readback/report.json   # -> tickets_blind_retry.jsonl
    python readback.py compare data/readback/extracted.jsonl [data/readback/extracted_retry.jsonl]

The agent prompt lives in agent-prompts/readback-check.md (gitignored).
"""
import argparse
import json
import re
from pathlib import Path

from policy import FACT_FIELDS, route
from tickets import FACTS_PATH, TICKETS_PATH, load_jsonl, make_state

READBACK_DIR = Path("data/readback")
REPORT_PATH = READBACK_DIR / "report.json"
UNKNOWN_BASES = {"not_stated", "conflicting"}

def write_blind(records, tickets, path, only_ids = None):
    """Write {id, state} lines for the reader; returns how many were written."""
    by_id = {t["id"]: t for t in tickets}
    path = Path(path)
    path.parent.mkdir(parents = True, exist_ok = True)
    n = 0
    with open(path, "w") as f:
        for r in records:
            if r["id"] not in by_id or (only_ids is not None and r["id"] not in only_ids):
                continue
            f.write(json.dumps({"id": r["id"], "state": make_state(r, by_id[r["id"]])}) + "\n")
            n += 1
    return n

def _number(value):
    """Parse 640, "640", "$2,300.50" into a float."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return float(re.sub(r"[^\d.]", "", str(value)))

def _cast(field, value):
    """Cast one extracted value to the type FACT_FIELDS expects."""
    if value is None:
        return None
    kind = FACT_FIELDS[field]
    if kind == "float":
        return _number(value)
    if kind == "int":
        return int(round(_number(value)))
    if kind == "bool":
        return value if isinstance(value, bool) else str(value).strip().lower() == "true"
    return str(value).strip().lower()

def extracted_facts(entry):
    """Map one agent extraction to a facts dict; not_stated/conflicting become None."""
    facts = {}
    for field in FACT_FIELDS:
        item = entry.get("facts", {}).get(field) or {}
        value = None if item.get("basis") in UNKNOWN_BASES else item.get("value")
        facts[field] = _cast(field, value)
    return facts

def _reasons(record, entry):
    """Why a ticket fails the read-back; [] means it passes."""
    if entry.get("flags", {}).get("names_routing"):
        return ["names_routing"]
    reasons = [
        f"conflicting: {field}" for field, item in entry.get("facts", {}).items()
        if (item or {}).get("basis") == "conflicting" and record["facts"].get(field) is not None
    ]
    try:
        decision = route(extracted_facts(entry))
    except ValueError as e:
        return [f"invalid extraction: {e}"] + reasons
    if decision.queue != record["queue"]:
        reasons.append(f"queue {record['queue']} != {decision.queue}")
    if decision.priority != record["priority"]:
        reasons.append(f"priority {record['priority']} != {decision.priority}")
    return reasons

def compare(records, extracted):
    """Check every record against its extraction (a dict keyed by id) and return the report."""
    report = {"total": len(records), "ok_ids": [], "failed": [], "missing": [], "unrealistic": []}
    for r in records:
        entry = extracted.get(r["id"])
        if entry is None:
            report["missing"].append(r["id"])
            continue
        if entry.get("flags", {}).get("unrealistic"):
            report["unrealistic"].append(r["id"])
        reasons = _reasons(r, entry)
        if reasons:
            report["failed"].append({"id": r["id"], "reasons": reasons})
        else:
            report["ok_ids"].append(r["id"])
    return report

def load_extractions(paths):
    """Merge agent output files by id; later files override earlier ones."""
    merged = {}
    for path in paths:
        for entry in load_jsonl(path):
            merged[entry["id"]] = entry
    return merged

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest = "command", required = True)
    blind = sub.add_parser("blind")
    blind.add_argument("--only-failed", help = "report.json: write only the ids that failed or were missing")
    cmp = sub.add_parser("compare")
    cmp.add_argument("files", nargs = "+")
    cmp.add_argument("--report", default = str(REPORT_PATH))
    args = parser.parse_args()

    records = load_jsonl(FACTS_PATH)
    if args.command == "blind":
        tickets = load_jsonl(TICKETS_PATH)
        only, out = None, READBACK_DIR / "tickets_blind.jsonl"
        if args.only_failed:
            prev = json.loads(Path(args.only_failed).read_text())
            only = {f["id"] for f in prev["failed"]} | set(prev["missing"])
            out = READBACK_DIR / "tickets_blind_retry.jsonl"
        print(f"Wrote {write_blind(records, tickets, out, only)} tickets to {out}")
        return

    report = compare(records, load_extractions(args.files))
    Path(args.report).write_text(json.dumps(report, indent = 2))
    print(f"{len(report['ok_ids'])}/{report['total']} passed, {len(report['failed'])} failed, "
          f"{len(report['missing'])} missing, {len(report['unrealistic'])} flagged unrealistic")
    for f in report["failed"]:
        print(f"  {f['id']}: {'; '.join(f['reasons'])}")
    print(f"Wrote {args.report}")

if __name__ == "__main__":
    main()
