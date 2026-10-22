import json
import sys
from pathlib import Path

from system1.main import create_app


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m system1.openapi_dump <out.json>")
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(create_app().openapi(), indent=2) + "\n")


if __name__ == "__main__":
    main()
