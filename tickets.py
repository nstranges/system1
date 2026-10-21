"""Build model-facing ticket state and check written tickets against their facts records.

    python tickets.py validate              # all 550 tickets must exist
    python tickets.py validate --partial    # while writing in batches: check only tickets written so far
"""
import argparse
import json
import re
import sys
from pathlib import Path

from facts_grid import LENGTH_BUCKETS
from policy import QUESTIONS_PATH

FACTS_PATH = Path("data/raw/facts.jsonl")
TICKETS_PATH = Path("data/raw/tickets.jsonl")
SUBJECT_WORDS = (3, 10)
LENGTH_SLACK = 10

# Team names that are also ordinary customer vocabulary ("sales tax", "does the API support...").
# These only count as a leak inside a routing phrase.
EVERYDAY = {"sales", "account access", "api support", "general support", "legacy api"}
ROUTING_PATTERNS = [
    r"\b{p}\s+(team|department|queue|desk|reps?)\b",
    r"\b(talk|speak|chat)\s+(to|with)\s+(your\s+|the\s+|a\s+|someone\s+(in|from)\s+)?{p}\b",
    r"\b(forward|pass|send|route|escalate)\b[^.]*\bto\s+(your\s+|the\s+)?{p}\b",
]

def load_jsonl(path):
    """Read a JSONL file into a list of dicts."""
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]

def make_state(record, ticket):
    """The model-facing state: the customer's message plus the CRM fields."""
    f = record["facts"]
    return {
        "ticket": {"subject": ticket["subject"], "body": ticket["body"], "created_at": record["created_at"]},
        "customer": {"plan": f["plan_tier"], "region": f["region"], "seats": f["seats"], "sso_enabled": f["sso_enabled"]},
    }

def _leak_patterns():
    """Compile one regex per way a ticket could name a queue."""
    queues = json.loads(QUESTIONS_PATH.read_text())["queues"]
    phrases = set()
    for key, entry in queues.items():
        name = entry["name"].lower()
        phrases |= {key, key.replace("_", " "), name, name.replace("&", "and")}
    patterns = []
    for p in phrases:
        escaped = re.escape(p).replace(r"\ ", r"\s+")
        if p in EVERYDAY:
            patterns += [re.compile(t.format(p = escaped), re.I) for t in ROUTING_PATTERNS]
        else:
            patterns.append(re.compile(rf"\b{escaped}\b", re.I))
    return patterns

def _amount_forms(amount):
    """Ways an amount may be written: 2300, 2,300, 2300.50, 2,300.50."""
    if float(amount).is_integer():
        return {f"{int(amount)}", f"{int(amount):,}"}
    return {f"{amount:.2f}", f"{amount:,.2f}"}

def _has_amount(text, amount):
    """True if the amount appears as a whole number in the text."""
    # A trailing comma is punctuation unless a digit follows it ("$2,300, which" vs "$2,3000")
    return any(re.search(rf"(?<![\d,.]){re.escape(form)}(?!\d|,\d)", text) for form in _amount_forms(amount))

def _has_version(text, version, implied):
    """True if the API version is recoverable; implied v1 may say legacy/old instead."""
    if re.search(rf"\b{version}\b", text, re.I):
        return True
    return implied and version == "v1" and re.search(r"\b(legacy|old|older|original)\b", text, re.I) is not None

def validate_tickets(records, tickets, partial = False):
    """Return human-readable problems; [] means every ticket is valid."""
    errors, patterns = [], _leak_patterns()
    by_id = {r["id"]: r for r in records}
    seen = set()

    for t in tickets:
        tid = t.get("id")
        if tid in seen:
            errors.append(f"{tid}: duplicate ticket id")
            continue
        seen.add(tid)
        if tid not in by_id:
            errors.append(f"{tid}: ticket has no facts record")
            continue
        r, subject, body = by_id[tid], t.get("subject", ""), t.get("body", "")
        text = f"{subject}\n{body}"

        if not SUBJECT_WORDS[0] <= len(subject.split()) <= SUBJECT_WORDS[1]:
            errors.append(f"{tid}: subject has {len(subject.split())} words (want {SUBJECT_WORDS[0]}-{SUBJECT_WORDS[1]})")
        lo, hi = LENGTH_BUCKETS[r["style"]["length"]]
        words = len(body.split())
        if not lo - LENGTH_SLACK <= words <= hi + LENGTH_SLACK:
            errors.append(f"{tid}: body has {words} words (bucket {r['style']['length']} is {lo}-{hi})")
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                errors.append(f"{tid}: queue leak '{match.group(0)}'")
                break
        f = r["facts"]
        if f["amount_usd"] is not None and not _has_amount(text, f["amount_usd"]):
            errors.append(f"{tid}: amount_usd {f['amount_usd']} not found in text")
        if f["api_version"] is not None and not _has_version(text, f["api_version"], r["style"]["implied_facts"]):
            errors.append(f"{tid}: api_version {f['api_version']} not recoverable from text")

    if not partial:
        errors += [f"{rid}: ticket missing" for rid in by_id if rid not in seen]
    return errors

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices = ["validate"])
    parser.add_argument("--facts", default = str(FACTS_PATH))
    parser.add_argument("--tickets", default = str(TICKETS_PATH))
    parser.add_argument("--partial", action = "store_true", help = "don't report tickets not written yet")
    args = parser.parse_args()

    records = load_jsonl(args.facts)
    tickets = load_jsonl(args.tickets) if Path(args.tickets).exists() else []
    errors = validate_tickets(records, tickets, partial = args.partial)
    for e in errors:
        print(e)
    print(f"{len(tickets)} tickets checked against {len(records)} records: {len(errors)} problems")
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
