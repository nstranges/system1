"""Tests for building ticket state and validating written tickets."""
from tickets import make_state, validate_tickets

def record(**overrides):
    """A facts record like those in data/raw/facts.jsonl."""
    base = {
        "id": "t0001", "created_at": "2026-09-10",
        "facts": {"plan_tier": "pro", "region": "eu", "seats": 12, "sso_enabled": False,
                  "issue_type": "refund_request", "secondary_issue": None, "amount_usd": 640,
                  "days_since_charge": 5, "api_version": None},
        "queue": "finance_review", "priority": "P3", "rule_id": "R04", "difficulty": "clear",
        "confusable_with": None,
        "style": {"tone": "calm", "length": "short", "typos": False, "implied_facts": False, "distractor": False},
    }
    return {**base, **overrides}

def ticket(body = None, subject = "Refund for my annual upgrade", tid = "t0001"):
    """A ticket with a short, clean body by default."""
    body = body or ("Hi there, five days ago I upgraded to the annual plan and was charged $640. "
                    "It turns out my team does not need the extra features after all, and nobody has used them yet. "
                    "Could you please refund the $640 to the card on file? Thanks so much for your help, Priya")
    return {"id": tid, "subject": subject, "body": body}

def test_make_state_layout():
    state = make_state(record(), ticket())
    assert set(state) == {"ticket", "customer"}
    assert state["ticket"] == {"subject": "Refund for my annual upgrade", "body": ticket()["body"], "created_at": "2026-09-10"}
    assert state["customer"] == {"plan": "pro", "region": "eu", "seats": 12, "sso_enabled": False}

def test_clean_ticket_passes():
    assert validate_tickets([record()], [ticket()]) == []

def test_flags_missing_and_extra_ids():
    errors = validate_tickets([record()], [ticket(tid = "t0002")])
    assert any("t0001" in e and "missing" in e for e in errors)
    assert any("t0002" in e and "no facts record" in e for e in errors)

def test_flags_duplicate_ticket_ids():
    assert any("duplicate" in e for e in validate_tickets([record()], [ticket(), ticket()]))

def test_flags_body_length_outside_bucket():
    long_body = ticket()["body"] + " More detail." * 40
    assert any("t0001" in e and "words" in e for e in validate_tickets([record()], [ticket(body = long_body)]))

def test_flags_queue_leak():
    for leak in ["Finance Review", "finance_review", "finance review"]:
        body = ticket()["body"] + f" Please pass this to {leak}."
        assert any("t0001" in e and "leak" in e for e in validate_tickets([record()], [ticket(body = body)])), leak

def test_everyday_words_are_not_leaks():
    body = ticket()["body"] + " Our sales tax setup is fine and I know the API support for webhooks is good."
    assert validate_tickets([record()], [ticket(body = body)]) == []

def test_routing_phrases_with_everyday_names_are_leaks():
    body = ticket()["body"] + " Maybe I should talk to your sales team."
    assert any("leak" in e for e in validate_tickets([record()], [ticket(body = body)]))

def test_flags_bad_subject_length():
    assert any("subject" in e for e in validate_tickets([record()], [ticket(subject = "Refund")]))

def test_flags_missing_amount():
    body = ticket()["body"].replace("$640", "the charge")
    assert any("amount" in e for e in validate_tickets([record()], [ticket(body = body)]))

def test_amount_with_thousands_separator_counts():
    facts = {**record()["facts"], "amount_usd": 2300}
    body = ticket()["body"].replace("$640", "$2,300")
    assert validate_tickets([record(facts = facts)], [ticket(body = body)]) == []

def test_flags_missing_api_version():
    facts = {**record()["facts"], "issue_type": "api_error", "amount_usd": None, "days_since_charge": None,
             "api_version": "v1"}
    body = ("Since this morning every call our integration makes to your API comes back with a 401 error, "
            "even though we have not rotated our keys or changed any code in weeks. We send around two hundred "
            "invoices a day through it so this is a real problem for us. Can someone take a look? Thanks, Omar")
    errors = validate_tickets([record(facts = facts)], [ticket(body = body, subject = "API calls failing with 401")])
    assert any("api_version" in e for e in errors)

def test_amount_followed_by_punctuation_counts():
    facts = {**record()["facts"], "amount_usd": 2300}
    body = ("Hi there, five days ago I upgraded to the annual plan and the charge was $2,300, which was a shock. "
            "It turns out my team does not need the extra features after all, and nobody has used them yet. "
            "Could you please refund that charge to the card on file? Thanks so much for your help, Priya")
    assert validate_tickets([record(facts = facts)], [ticket(body = body)]) == []

def test_amount_inside_larger_number_does_not_count():
    facts = {**record()["facts"], "amount_usd": 640}
    body = ticket()["body"].replace("$640", "$6,400")
    assert any("amount" in e for e in validate_tickets([record(facts = facts)], [ticket(body = body)]))
