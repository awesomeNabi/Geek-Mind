#!/usr/bin/env python3
"""Validate that the vendored Mid360 service is portable and source-only."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "service" / "unitree_native_slam" / "autonomy_mid360"
SOURCE_PACKAGES = (
    "far_planner",
    "fast_lio",
    "go2_sport_api",
    "graph_decoder",
    "livox_ros_driver2",
    "local_planner",
    "mid360_go2_nav_bridge",
    "open3d_loc",
    "terrain_analysis",
    "terrain_analysis_ext",
    "unitree_api",
    "unitree_go",
    "visibility_graph_msg",
)
REQUIRED_FILES = (
    SERVICE / "docker" / "Dockerfile.humble",
    SERVICE / "config" / "unitree_go2_fastlio_autonomy.yaml",
    SERVICE / "prior_graphs" / "my_prior_graph_final.vgh",
    SERVICE / "scripts" / "build_image.sh",
    SERVICE / "scripts" / "check_vgraph_ready.py",
    SERVICE / "scripts" / "run_container.sh",
    SERVICE / "scripts" / "start_fastlio_unitree_autonomy_for_nav.sh",
    SERVICE / "scripts" / "start_nav.sh",
    SERVICE / "scripts" / "publish_goal.sh",
    SERVICE / "scripts" / "publish_navigation_boundary.sh",
    SERVICE / "third_party" / "Livox-SDK2" / "LICENSE.txt",
    *(SERVICE / "workspace" / "src" / package / "package.xml" for package in SOURCE_PACKAGES),
)
FORBIDDEN_DIRECTORY_NAMES = {".git", "build", "install", "log", "logs", "__pycache__"}
LEGACY_RUNTIME_PATHS = (
    "/home/unitree/go2-fast-lio",
    "/workspace/nav_ws",
    "/workspace/autonomy-go2-mid360",
    "mid360_go2_nav_humble",
)
RUNTIME_TEXT_SUFFIXES = {".json", ".json5", ".py", ".sh", ".yaml", ".yml"}
GITHUB_FILE_LIMIT = 100 * 1024 * 1024


def source_control_files() -> list[Path]:
    """Return tracked and unignored candidate files below the service root."""
    service_relative = SERVICE.relative_to(ROOT)
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
                "--",
                str(service_relative),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        result = None

    if result is not None and result.returncode == 0:
        return sorted(ROOT / value for value in result.stdout.split("\0") if value)
    return sorted(path for path in SERVICE.rglob("*") if path.is_file())


def validate_service() -> list[str]:
    """Return portability errors for the bundled Mid360 service."""
    errors: list[str] = []

    for path in REQUIRED_FILES:
        if not path.is_file():
            errors.append(f"required service file is missing: {path}")

    candidate_files = source_control_files()
    forbidden_directories: set[Path] = set()
    for path in candidate_files:
        relative_parts = path.relative_to(SERVICE).parts[:-1]
        for index, part in enumerate(relative_parts):
            if part in FORBIDDEN_DIRECTORY_NAMES:
                forbidden_directories.add(SERVICE.joinpath(*relative_parts[: index + 1]))
        if not path.is_file():
            continue
        if path.stat().st_size >= GITHUB_FILE_LIMIT:
            errors.append(f"file exceeds GitHub's 100 MiB limit: {path}")
        if path.suffix.lower() == ".pcd":
            errors.append(f"captured PCD map must stay outside source control: {path}")
        if path.suffix.lower() not in RUNTIME_TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in LEGACY_RUNTIME_PATHS:
            if marker in text:
                errors.append(f"legacy runtime path {marker!r} remains in {path}")

    for path in sorted(forbidden_directories):
        errors.append(f"generated directory must not be bundled: {path}")

    for script in sorted((SERVICE / "scripts").glob("*.sh")):
        if not script.stat().st_mode & 0o111:
            errors.append(f"service script is not executable: {script}")
            continue
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True, check=False)
        if result.returncode:
            errors.append(f"invalid shell syntax in {script}: {result.stderr.strip()}")

    return errors


def main() -> int:
    """Print validation errors or a compact success summary."""
    errors = validate_service()
    if errors:
        print("Mid360 service validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    files = [path for path in source_control_files() if path.is_file()]
    file_count = len(files)
    total_bytes = sum(path.stat().st_size for path in files)
    print(
        f"OK: portable Mid360 service contains {file_count} source/runtime files ({total_bytes / 1024 / 1024:.1f} MiB)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
