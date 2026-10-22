import json
from pathlib import Path

from system1.contracts.datasets import DatasetRow


class JsonlDatasetSource:
    """One DatasetRow per line."""

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def rows(self, split: str | None = None) -> list[DatasetRow]:
        if not self.path.exists():
            return []
        rows = [DatasetRow(**json.loads(line)) for line in self.path.read_text().splitlines() if line.strip()]
        return [r for r in rows if split is None or r.split == split]
