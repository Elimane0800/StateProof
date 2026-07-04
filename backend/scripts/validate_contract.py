"""Validate a payload against packages/contract/schema.json.

Usage:
    python backend/scripts/validate_contract.py packages/contract/contract.example.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "packages" / "contract" / "schema.json"


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else REPO_ROOT / "packages" / "contract" / "contract.example.json"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = json.loads(target.read_text(encoding="utf-8"))

    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        print(f"INVALID: {target}")
        for err in errors:
            loc = "/".join(str(p) for p in err.path) or "<root>"
            print(f"  - {loc}: {err.message}")
        return 1

    print(f"VALID: {target} matches {SCHEMA_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
