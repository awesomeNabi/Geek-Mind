"""Paths shared by both Python environments."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# In the repository, external environments are siblings of Geek-Mind.
# A standalone copy can still use siblings of the integration directory.
WORKSPACE = ROOT.parents[2] if ROOT.parent.name == "integrations" else ROOT.parent
MAGIC_ROOT = Path(os.environ.get("MAGIC_ROOT", WORKSPACE / "MAGIC"))
DUCK_ROOT = Path(os.environ.get("MICRODUCK_ROOT", WORKSPACE / "microduck_ros2"))
STATE = Path(os.environ.get("MAGIC_DUCK_STATE", ROOT / ".runtime"))
URL = os.environ.get("MICRODUCK_BRIDGE_URL", "http://127.0.0.1:8766")
