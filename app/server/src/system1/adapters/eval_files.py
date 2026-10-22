import json
from pathlib import Path

from system1.contracts.evaluation import EvalRecord, EvalRun


class EvalFilesSource:
    """Reads `<prefix>_predictions.jsonl` and `<prefix>_summary.json` as eval_common.py writes them."""

    def __init__(self, dir: Path, models: dict[str, str]):
        self.dir = Path(dir)
        self.models = models

    def runs(self) -> list[EvalRun]:
        runs = []
        for model_key, prefix in self.models.items():
            predictions = self.dir / f"{prefix}_predictions.jsonl"
            summary_file = self.dir / f"{prefix}_summary.json"
            if not (predictions.exists() and summary_file.exists()):
                continue
            summary = json.loads(summary_file.read_text())
            records = [
                EvalRecord(**{k: raw.get(k) for k in EvalRecord.model_fields})
                for raw in map(json.loads, predictions.read_text().splitlines())
                if raw
            ]
            runs.append(
                EvalRun(
                    model_key=model_key,
                    label=summary.get("model", prefix),
                    summary=summary,
                    records=records,
                    is_fixture=bool(summary.get("fixture", False)),
                )
            )
        return runs
