"""Use-case gallery: static templates plus the flagship project's assets.

gallery.json holds every template. The flagship entry (Tallyfern) carries a
`flagship` block instead of an inline policy: its policy, samples and eval
results are generated into data/tallyfern/ by scripts/build_flagship.py.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from system1.domain.policy import Policy

DATA_DIR = Path(__file__).parent / "data"


class FlagshipAssets(BaseModel):
    samples_path: Path
    eval_dir: Path
    eval_models: dict[str, str]
    jev_questions_path: Path
    model_label: str


class Template(BaseModel):
    id: str
    name: str
    summary: str
    fit: Literal["good", "workable", "poor"]
    fit_reasons: list[str]
    policy: Policy
    sample_inputs: list[str]
    flagship: FlagshipAssets | None = None


def _build(entry: dict) -> Template:
    entry = dict(entry)
    flagship = entry.pop("flagship", None)
    if flagship is None:
        return Template(**entry)
    folder = DATA_DIR / flagship["folder"]
    entry["policy"] = json.loads((folder / "policy.json").read_text())
    assets = FlagshipAssets(
        samples_path=folder / "samples.jsonl",
        eval_dir=folder / "eval",
        eval_models=flagship["eval_models"],
        jev_questions_path=folder / "jev_questions.json",
        model_label=flagship["model_label"],
    )
    return Template(**entry, flagship=assets)


def load_templates() -> list[Template]:
    entries = json.loads((DATA_DIR / "gallery.json").read_text())
    return [_build(entry) for entry in entries]


def get_template(template_id: str) -> Template:
    for template in load_templates():
        if template.id == template_id:
            return template
    raise KeyError(template_id)
