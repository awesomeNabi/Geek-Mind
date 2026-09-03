import sys
from pathlib import Path

import json5

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from validate_mid360_service import SERVICE, validate_service  # noqa: E402


CONFIG = ROOT / "config" / "unitree_go2_koala_fetch_single_mode_autonomy_mid360.json5"


def _navigation(config: dict) -> dict:
    return next(action for action in config["agent_actions"] if action["llm_label"] == "navigate_location")


def _startup(config: dict) -> dict:
    return next(
        hook["handler_config"]
        for hook in config["lifecycle_hooks"]
        if hook["handler_type"] == "function"
        and hook["handler_config"].get("function") == "start_autonomy_mid360_nav_hook"
    )


def test_mid360_config_uses_bundled_service_and_unified_ros_install():
    config = json5.loads(CONFIG.read_text(encoding="utf-8"))
    navigation = _navigation(config)["config"]
    startup = _startup(config)

    assert navigation["container_name"] == "magic_mini_mid360_nav"
    assert navigation["goal_script"].endswith("/service/unitree_native_slam/autonomy_mid360/scripts/publish_goal.sh")
    assert startup["base_dir"].endswith("/service/unitree_native_slam/autonomy_mid360")
    assert navigation["workspace_setup"] == "/opt/unitree_native_slam/install/setup.bash"
    assert startup["workspace_setup"] == navigation["workspace_setup"]
    assert startup["prior_graph_file"] == "/workspace/unitree_native_slam/prior_graphs/my_prior_graph_final.vgh"


def test_mid360_service_is_source_only_and_portable():
    assert SERVICE.is_dir()
    assert validate_service() == []


def test_mid360_docker_build_uses_tuna_mirrors_and_visible_stages():
    dockerfile = (SERVICE / "docker" / "Dockerfile.humble").read_text(encoding="utf-8")
    build_script = (SERVICE / "scripts" / "build_image.sh").read_text(encoding="utf-8")

    assert "https://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports" in dockerfile
    assert "https://mirrors.tuna.tsinghua.edu.cn/ros2/ubuntu" in dockerfile
    assert "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple" in dockerfile
    assert "USE_TUNA_MIRROR" in build_script
    assert "[preflight 1/2]" in build_script
    for stage in range(1, 7):
        assert f"[stage {stage}/6]" in dockerfile
