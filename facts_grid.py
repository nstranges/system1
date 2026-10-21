"""Seeded grid of ticket facts. Every ticket's facts, and so its label, are fixed before any text is written.

    python facts_grid.py --n 550 --seed 20261020 --out data/raw/facts.jsonl
"""
import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

from policy import QUEUES, route

# Word counts per body length. Conservative caps until Laya's window is measured (plan Task 3)
LENGTH_BUCKETS = {"short": (40, 70), "medium": (70, 110), "long": (110, 150)}
DIFFICULTY_MIX = {"clear": 0.5, "borderline": 0.3, "tricky": 0.2}
TONES = ("calm", "angry", "terse", "rambling")

# Which queue a borderline ticket should plausibly be mistaken for
CONFUSABLE = {
    "trust_safety": "account_access", "incident_response": "api_support", "billing_disputes": "billing_refunds",
    "finance_review": "billing_refunds", "billing_refunds": "finance_review", "payments_ops": "trust_safety",
    "legacy_api": "api_support", "api_support": "legacy_api", "enterprise_identity": "account_access",
    "account_access": "trust_safety", "privacy_legal": "general_support", "sales": "general_support",
    "general_support": "privacy_legal",
}
OVERRIDES = {"trust_safety": "security_concern", "incident_response": "outage_report",
             "billing_disputes": "chargeback_dispute"}
# Main requests that can sit under an override without outranking it
OVERRIDE_PRIMARIES = {
    "trust_safety": ["login_problem", "failed_payout", "billing_question", "how_to", "api_error"],
    "incident_response": ["api_error", "failed_payout", "billing_question", "how_to", "refund_request"],
    "billing_disputes": ["refund_request", "billing_question", "failed_payout"],
}
SIDE_ISSUES = ["how_to", "billing_question", "plan_change"]

PLANS, PLAN_WEIGHTS = ("free", "starter", "pro", "enterprise"), (10, 25, 40, 25)
SEATS = {"free": (1, 3), "starter": (1, 10), "pro": (5, 60), "enterprise": (50, 2000)}
REGIONS, REGION_WEIGHTS = ("us", "ca", "eu", "uk", "apac"), (40, 10, 20, 15, 15)
FIRST_DAY, LAST_OFFSET = date(2026, 8, 1), 75   # 2026-08-01 .. 2026-10-15

def _account(rng, plans = PLANS, regions = REGIONS, sso = None, seats = None):
    """Sample the CRM fields; sso=None means 70% on for enterprise, always off otherwise."""
    weights = [PLAN_WEIGHTS[PLANS.index(p)] for p in plans]
    plan = rng.choices(plans, weights)[0]
    region = rng.choices(regions, [REGION_WEIGHTS[REGIONS.index(r)] for r in regions])[0]
    if sso is None:
        sso = plan == "enterprise" and rng.random() < 0.7
    return {
        "plan_tier": plan, "region": region,
        "seats": seats if seats is not None else rng.randint(*SEATS[plan]),
        "sso_enabled": sso,
        "issue_type": None, "secondary_issue": None, "amount_usd": None,
        "days_since_charge": None, "api_version": None,
    }

def _maybe(rng, p, value):
    """Return value with probability p, else None."""
    return value if rng.random() < p else None

def _issue_details(rng, issue, f):
    """Fill plausible amount/timing/version fields for a main request that doesn't decide the label."""
    if issue in ("refund_request", "chargeback_dispute"):
        f["amount_usd"] = _maybe(rng, 0.6, rng.randint(20, 3000))
        f["days_since_charge"] = _maybe(rng, 0.5, rng.randint(1, 90))
    elif issue == "failed_payout":
        f["amount_usd"] = _maybe(rng, 0.7, rng.randint(150, 40000))
    elif issue == "api_error":
        f["api_version"] = rng.choice(["v1", "v2", None])

def _refund(rng, f, difficulty, late_or_large):
    """Refund facts that route to finance_review (late_or_large) or billing_refunds."""
    f["issue_type"] = "refund_request"
    if difficulty == "borderline":
        if rng.random() < 0.5:   # amount near $500
            f["amount_usd"] = rng.randint(501, 550) if late_or_large else rng.randint(450, 500)
            f["days_since_charge"] = _maybe(rng, 0.7, rng.randint(1, 24))
        else:                    # timing near 30 days
            f["days_since_charge"] = rng.randint(31, 33) if late_or_large else rng.randint(27, 30)
            f["amount_usd"] = _maybe(rng, 0.7, rng.randint(20, 420))
    elif late_or_large:
        if rng.random() < 0.5:
            f["amount_usd"], f["days_since_charge"] = rng.randint(700, 4000), _maybe(rng, 0.7, rng.randint(1, 24))
        else:
            f["amount_usd"], f["days_since_charge"] = _maybe(rng, 0.7, rng.randint(20, 400)), rng.randint(45, 120)
    else:
        f["amount_usd"] = _maybe(rng, 0.85, rng.randint(15, 400))
        f["days_since_charge"] = _maybe(rng, 0.85, rng.randint(0, 24))

def _sample(queue, difficulty, with_secondary, rng):
    """Sample facts that route to `queue`; returns (facts, confusable_with)."""
    confusable = None
    if difficulty == "borderline":
        confusable = CONFUSABLE[queue]

    if queue in OVERRIDES:
        f = _account(rng)
        if with_secondary:
            f["issue_type"] = rng.choice(OVERRIDE_PRIMARIES[queue])
            _issue_details(rng, f["issue_type"], f)
            f["secondary_issue"] = OVERRIDES[queue]
        else:
            f["issue_type"] = OVERRIDES[queue]
            _issue_details(rng, f["issue_type"], f)
        return f, confusable

    if queue in ("finance_review", "billing_refunds"):
        f = _account(rng)
        _refund(rng, f, difficulty, queue == "finance_review")
        confusable = None
    elif queue == "payments_ops":
        f = _account(rng)
        f["issue_type"] = "failed_payout"
        if difficulty == "borderline":
            f["amount_usd"], confusable = rng.randint(9000, 11000), None
        else:
            f["amount_usd"] = rng.choice([rng.randint(150, 8000), rng.randint(12000, 40000)])
    elif queue in ("legacy_api", "api_support"):
        f = _account(rng)
        f["issue_type"] = "api_error"
        f["api_version"] = "v1" if queue == "legacy_api" else rng.choice(["v2", "v2", None])
    elif queue == "enterprise_identity":
        f = _account(rng, plans = ("enterprise",), sso = True)
        f["issue_type"] = "login_problem"
    elif queue == "account_access":
        f = _account(rng, sso = False)
        f["issue_type"] = "login_problem"
    elif queue == "privacy_legal":
        f = _account(rng, regions = ("eu", "uk"))
        f["issue_type"] = "data_request"
    elif queue == "sales":
        if difficulty == "borderline":
            f = _account(rng, plans = ("pro",), seats = rng.randint(50, 55))
            confusable = None
        else:
            f = _account(rng, plans = ("enterprise",))
        f["issue_type"] = "plan_change"
    else:   # general_support
        if difficulty == "borderline" and rng.random() < 0.5:
            f = _account(rng, plans = ("pro",), seats = rng.randint(45, 49))
            f["issue_type"], confusable = "plan_change", "sales"
        elif difficulty == "borderline":
            f = _account(rng, regions = ("us", "ca", "apac"))
            f["issue_type"] = "data_request"
        else:
            f = _account(rng)
            f["issue_type"] = rng.choice(["billing_question", "how_to"])

    if with_secondary:
        f["secondary_issue"] = rng.choice([s for s in SIDE_ISSUES if s != f["issue_type"]])
    return f, confusable

def _style(rng, difficulty, with_secondary):
    """Writing hints for one ticket."""
    tone = rng.choice(TONES)
    if tone == "terse":
        length = rng.choice(["short", "short", "medium"])
    elif tone == "rambling":
        length = rng.choice(["medium", "long", "long"])
    else:
        length = rng.choices(["short", "medium", "long"], [35, 45, 20])[0]
    tricky = difficulty == "tricky"
    return {
        "tone": tone, "length": length, "typos": rng.random() < 0.25,
        "implied_facts": tricky and not with_secondary,
        "distractor": tricky and rng.random() < 0.3,
    }

def build_grid(n, seed, id_start = 1):
    """Return n facts records, balanced over queues and difficulties, labelled by policy.route."""
    rng = random.Random(seed)
    plan = []
    for i, queue in enumerate(QUEUES):
        k = n // len(QUEUES) + (1 if i < n % len(QUEUES) else 0)
        clear, borderline = round(DIFFICULTY_MIX["clear"] * k), round(DIFFICULTY_MIX["borderline"] * k)
        tricky = k - clear - borderline
        plan += [(queue, "clear", False)] * clear + [(queue, "borderline", False)] * borderline
        plan += [(queue, "tricky", True)] * (tricky // 2) + [(queue, "tricky", False)] * (tricky - tricky // 2)

    records = []
    for queue, difficulty, with_secondary in plan:
        facts, confusable = _sample(queue, difficulty, with_secondary, rng)
        decision = route(facts)
        assert decision.queue == queue, (queue, difficulty, facts)
        records.append({
            "created_at": (FIRST_DAY + timedelta(days = rng.randint(0, LAST_OFFSET))).isoformat(),
            "facts": facts, "queue": decision.queue, "priority": decision.priority,
            "rule_id": decision.rule_id, "difficulty": difficulty, "confusable_with": confusable,
            "style": _style(rng, difficulty, with_secondary),
        })

    rng.shuffle(records)
    return [{"id": f"t{id_start + i:04d}", **r} for i, r in enumerate(records)]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type = int, default = 550)
    parser.add_argument("--seed", type = int, default = 20261020)
    parser.add_argument("--id-start", type = int, default = 1)
    parser.add_argument("--out", default = "data/raw/facts.jsonl")
    args = parser.parse_args()

    records = build_grid(args.n, args.seed, args.id_start)
    out = Path(args.out)
    out.parent.mkdir(parents = True, exist_ok = True)
    with open(out, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"Wrote {len(records)} records to {out}")

if __name__ == "__main__":
    main()
