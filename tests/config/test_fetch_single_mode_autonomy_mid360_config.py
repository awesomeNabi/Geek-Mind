import importlib
import os
import re
from pathlib import Path

import json5

from inputs import find_module_with_class


REPO_ROOT = Path(__file__).resolve().parents[2]
MERGED_CONFIG_PATH = REPO_ROOT / "config" / "unitree_go2_koala_fetch_single_mode_autonomy_mid360.json5"
FETCH_CONFIG_PATH = REPO_ROOT / "config" / "unitree_go2_koala_fetch_single_mode.json5"


def _load(path: Path) -> dict:
    with path.open("r") as f:
        return json5.load(f)


def _expand(value: str) -> str:
    pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2)
        return os.environ.get(name, default if default is not None else match.group(0))

    return pattern.sub(replace, value)


def _action(config: dict, label: str) -> dict:
    return next(action for action in config["agent_actions"] if action["llm_label"] == label)


def _input(config: dict, input_type: str) -> dict:
    return next(entry for entry in config["agent_inputs"] if entry["type"] == input_type)


def _hook(config: dict, function_name: str) -> dict:
    return next(
        hook
        for hook in config["lifecycle_hooks"]
        if hook["handler_type"] == "function" and hook["handler_config"]["function"] == function_name
    )


def test_mid360_variant_replaces_navigation_and_preserves_fetch_actions():
    merged = _load(MERGED_CONFIG_PATH)
    fetch = _load(FETCH_CONFIG_PATH)

    input_types = {entry["type"] for entry in merged["agent_inputs"]}
    assert {"AutonomyLocationsInput", "AutonomyNavigationStatusInput"}.issubset(input_types)
    assert {
        "UnitreeNativeLocationsInput",
        "NativeNavigationStatusInput",
        "NativeSlamLocalizationInput",
    }.isdisjoint(input_types)
    assert find_module_with_class("AutonomyLocationsInput") == "autonomy_locations_input"
    assert find_module_with_class("AutonomyNavigationStatusInput") == "autonomy_navigation_status_input"

    navigation = _action(merged, "navigate_location")
    assert navigation["connector"] == "autonomy_mid360_nav"
    assert navigation["config"]["stand_up_before_navigation"] is True
    assert navigation["config"]["allow_real_robot_goal"] is True
    assert navigation["config"]["status_variable_key"] == "native_navigation_status"
    importlib.import_module("actions.navigate_location.connector.autonomy_mid360_nav")

    locations_input = _input(merged, "AutonomyLocationsInput")
    status_input = _input(merged, "AutonomyNavigationStatusInput")
    mission = next(
        background for background in merged["backgrounds"] if background["type"] == "KoalaFetchMissionContext"
    )
    assert navigation["config"]["locations_file"] == locations_input["config"]["locations_file"]
    assert status_input["config"]["status_variable_key"] == "native_navigation_status"
    assert mission["config"]["native_navigation_status_key"] == "native_navigation_status"
    assert mission["config"]["require_home_pose_match"] is False

    merged_non_navigation_actions = [
        action for action in merged["agent_actions"] if action["llm_label"] != "navigate_location"
    ]
    fetch_non_navigation_actions = [
        action for action in fetch["agent_actions"] if action["llm_label"] != "navigate_location"
    ]
    assert merged_non_navigation_actions == fetch_non_navigation_actions
    assert merged["voice_task_planner"] == fetch["voice_task_planner"]
    assert merged["voice_task_planner_llm"] == fetch["voice_task_planner_llm"]


def test_mid360_variant_has_guarded_lifecycle_and_local_files():
    os.environ.setdefault("MAGIC_DIR", str(REPO_ROOT))
    merged = _load(MERGED_CONFIG_PATH)
    navigation = _action(merged, "navigate_location")
    startup = _hook(merged, "start_autonomy_mid360_nav_hook")
    shutdown = _hook(merged, "stop_autonomy_mid360_nav_hook")

    assert startup["on_failure"] == "abort"
    assert startup["handler_config"]["real_robot"] is navigation["config"]["allow_real_robot_goal"]
    assert shutdown["handler_config"]["stop_container_on_shutdown"] is False
    assert not any(
        hook["handler_type"] == "function"
        and hook["handler_config"].get("function") in {"go2_stand_up_hook", "go2_stand_down_hook"}
        for hook in merged["lifecycle_hooks"]
    )

    assert Path(_expand(navigation["config"]["locations_file"])).is_file()
    assert Path(_expand(navigation["config"]["goal_script"])).is_file()
    prompt_path = Path(_expand(merged["system_prompt_path"]))
    assert prompt_path.is_file()
    prompt = prompt_path.read_text()
    assert "AutonomyLocations" in prompt
    assert "AutonomyNavigationStatus" in prompt
    assert "NativeSlamLocalizationStatus" not in prompt
