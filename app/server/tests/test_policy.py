import json
from pathlib import Path

import pytest

from system1.domain.policy import InputField, Option, Policy, Rule, validate_policy
from system1.domain.questions import build_questions

RULES = Path(__file__).parents[1] / "src/system1/templates/data/tallyfern/rules.json"


def make_policy(**overrides) -> Policy:
    base = {
        "decision_question": "Which team?",
        "inputs": [InputField(key="amount", label="Amount", type="float")],
        "options": [Option(key="a", name="A", covers=["x"]), Option(key="b", name="B", excludes=["y"])],
        "rules": [
            Rule(id="R1", text="Big amounts go to a.", label="a", when={"field": "amount", "op": "gt", "value": 5}),
            Rule(id="R2", text="Everything else goes to b.", label="b"),
        ],
    }
    return Policy.model_validate({**base, **overrides})


def test_valid_policy_has_no_issues():
    assert validate_policy(make_policy()) == []


def test_validate_rejects_unknown_label_duplicates_and_option_count():
    bad_label = make_policy(rules=[Rule(id="R1", text="t", label="zzz")])
    assert len(validate_policy(bad_label)) == 1

    dupes = make_policy(
        options=[Option(key="a", name="A"), Option(key="a", name="B")], rules=[Rule(id="R1", text="t", label="a")]
    )
    assert len(validate_policy(dupes)) == 1

    many = [Option(key=f"o{i}", name=f"O{i}") for i in range(16)]
    assert len(validate_policy(make_policy(options=many, rules=[Rule(id="R1", text="t", label="o0")]))) == 1

    single = make_policy(options=[Option(key="a", name="A")], rules=[Rule(id="R1", text="t", label="a")])
    assert len(validate_policy(single)) == 1

    unknown_input = make_policy(
        rules=[
            Rule(id="R1", text="t", label="a", when={"all": [{"field": "nope", "op": "eq", "value": 1}]}),
        ]
    )
    assert len(validate_policy(unknown_input)) == 1


def test_build_questions_policy_variant_shape():
    policy = make_policy()
    q = build_questions(policy, "policy", order=["b", "a"])
    spec = q["decision"]
    assert spec["type"] == "choice"
    assert list(spec["criteria"]) == ["b", "a"]
    assert spec["instructions"] == {"question": "Which team?", "precedence": [r.text for r in policy.rules]}
    assert spec["criteria"]["a"] == {"covers": ["x"], "excludes": []}
    labels = build_questions(policy, "labels")["decision"]
    assert labels["criteria"] == {"a": "A", "b": "B"}


def test_build_questions_rejects_invalid_policy():
    with pytest.raises(ValueError):
        build_questions(make_policy(rules=[Rule(id="R1", text="t", label="zzz")]), "labels")


def test_validate_rejects_non_snake_case_option_keys():
    policy = make_policy(
        options=[Option(key="Billing Team", name="A"), Option(key="a-b", name="B")],
        rules=[Rule(id="R1", text="t", label="Billing Team")],
    )
    issues = validate_policy(policy)
    assert [i.path for i in issues] == ["options[0].key", "options[1].key"]
    assert all("snake_case" in i.message for i in issues)


def test_tallyfern_option_keys_are_snake_case():
    from system1.domain.policy import SNAKE_CASE

    labels = {r["label"] for r in json.loads(RULES.read_text())}
    assert len(labels) == 13 and all(SNAKE_CASE.fullmatch(k) for k in labels)


def test_guidelines_and_samples_validated():
    assert validate_policy(make_policy(guidelines=["ok"] * 20, sample_inputs=["hi"] * 3)) == []

    too_many = validate_policy(make_policy(guidelines=["g"] * 21))
    assert [i.path for i in too_many] == ["guidelines"]

    too_long = validate_policy(make_policy(guidelines=["x" * 301]))
    assert len(too_long) == 1

    assert [i.path for i in validate_policy(make_policy(sample_inputs=["s"] * 4))] == ["sample_inputs"]
    assert len(validate_policy(make_policy(sample_inputs=["s" * 6001]))) == 1


def test_policy_question_includes_guidelines():
    p = make_policy(guidelines=["Be kind.", "Prefer b when unsure."])
    instructions = build_questions(p, "policy")["decision"]["instructions"]
    assert instructions["guidelines"] == p.guidelines
    assert instructions["precedence"] == [r.text for r in p.rules]

    bare = build_questions(make_policy(rules=[], guidelines=[]), "policy")["decision"]["instructions"]
    assert bare == {"question": "Which team?"}


def test_preview_trainer_finishes_as_preview():
    from system1.adapters.fakes import PreviewTrainer

    trainer = PreviewTrainer(duration_s=0)
    job = trainer.start("dataset-1", {})
    assert job.status == "queued"
    assert trainer.status(job.id).status == "running"
    done = trainer.status(job.id)
    assert done.status == "preview"
    assert done.message == "Real training connects soon."
    assert done.adapter_ref is None
