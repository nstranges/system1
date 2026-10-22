from system1.domain.policy import validate_policy
from system1.templates.catalog import get_template, load_templates


def test_templates_load_and_policies_are_valid():
    templates = load_templates()
    assert len(templates) == 10
    for template in templates:
        assert validate_policy(template.policy) == [], template.id
    flagship = get_template("tallyfern-triage").flagship
    assert flagship is not None
    assert flagship.samples_path.exists()
