#!/usr/bin/env python3
"""Lightweight local file validation for MAGIC_MINI."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import json5
from jsonschema import validate

from validate_mid360_service import validate_service


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = (
    ROOT / "config" / "unitree_go2_koala_fetch_single_mode.json5",
    ROOT / "config" / "unitree_go2_koala_fetch_single_mode_autonomy_mid360.json5",
)
SINGLE_MODE_SCHEMA = ROOT / "config" / "schema" / "single_mode_schema.json"


def expand_env(value: str) -> str:
    """Expand the ``${NAME:-default}`` expressions used by JSON5 configs."""
    pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2)
        return os.environ.get(name, default if default is not None else match.group(0))

    return pattern.sub(replace, value)


def walk_values(value: Any):
    """Yield every string nested in dictionaries and lists."""
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child)
    elif isinstance(value, str):
        yield value


def main() -> int:
    """Validate MINI configs and report their local and external paths."""
    os.environ.setdefault("MAGIC_DIR", str(ROOT))
    schema = json5.loads(SINGLE_MODE_SCHEMA.read_text(encoding="utf-8"))
    local_paths: set[Path] = set()
    external_paths: set[Path] = set()

    for config in CONFIGS:
        raw = json5.loads(config.read_text(encoding="utf-8"))
        validate(instance=raw, schema=schema)
        for text in walk_values(raw):
            expanded = expand_env(text)
            if not expanded.startswith("/"):
                continue
            path = Path(expanded)
            if str(path).startswith(str(ROOT)):
                local_paths.add(path)
            else:
                external_paths.add(path)

    missing = sorted(path for path in local_paths if not path.exists())
    if missing:
        print("Missing MAGIC_MINI local files:")
        for path in missing:
            print(f"  - {path}")
        return 1

    service_errors = validate_service()
    if service_errors:
        print("Mid360 service validation failed:")
        for error in service_errors:
            print(f"  - {error}")
        return 1

    print(f"OK: {len(CONFIGS)} configs passed schema validation and {len(local_paths)} local file paths exist.")
    if external_paths:
        print("External absolute references still present:")
        for path in sorted(external_paths):
            print(f"  - {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
