import pytest

from system1.domain.policy import InputField, Option, Policy, Rule, validate_policy
from system1.domain.questions import build_questions


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
