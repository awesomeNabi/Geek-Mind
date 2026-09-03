import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SCRIPT = ROOT / "service/unitree_native_slam/autonomy_mid360/scripts/mid360_runtime.sh"


def _resolve_paths(runtime: str, workspace: str) -> list[str]:
    command = f"""
set -euo pipefail
source {RUNTIME_SCRIPT!s}
mid360_default_workspace_dir
mid360_service_config_dir
mid360_prior_graph_file
"""
    env = {
        **os.environ,
        "MAGIC_DIR": "/tmp/magic-mini-runtime-test",
        "MID360_RUNTIME": runtime,
        "MID360_WORKSPACE_DIR": workspace,
    }
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", command],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.splitlines()


def test_docker_paths_ignore_host_workspace_override() -> None:
    assert _resolve_paths("docker", "/host/navigation/workspace") == [
        "/opt/unitree_native_slam",
        "/workspace/unitree_native_slam/config",
        "/workspace/unitree_native_slam/prior_graphs/my_prior_graph_final.vgh",
    ]


def test_host_paths_use_workspace_override() -> None:
    assert _resolve_paths("host", "/host/navigation/workspace") == [
        "/host/navigation/workspace",
        "/host/navigation/workspace/config",
        "/host/navigation/workspace/prior_graphs/my_prior_graph_final.vgh",
    ]
