import os
import re
from pathlib import Path

import json5
import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "unitree_go2_koala_nav_vision_no_arm.json5"
SCHEMA_PATH = ROOT / "config" / "schema" / "single_mode_schema.json"
FASTLIO_CONFIG_PATH = (
    ROOT / "service" / "unitree_native_slam" / "autonomy_mid360" / "config" / "unitree_go2_fastlio_autonomy.yaml"
)
FASTLIO_START_PATH = (
    ROOT
    / "service"
    / "unitree_native_slam"
    / "autonomy_mid360"
    / "scripts"
    / "start_fastlio_go2_livox_autonomy_for_nav.sh"
)


def _expand(value: str) -> str:
    pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")
    return pattern.sub(lambda match: os.environ.get(match.group(1), match.group(2) or match.group(0)), value)


def test_no_arm_config_is_schema_valid_and_excludes_arm_components():
    config = json5.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    schema = json5.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(config, schema)

    assert {action["llm_label"] for action in config["agent_actions"]} == {"speak", "navigate_location"}
    assert {background["type"] for background in config["backgrounds"]} == {"D435", "UnitreeGo2State"}
    assert not any(
        "arm:" in capability
        for entry in config["agent_inputs"] + config["backgrounds"]
        for capability in entry.get("requires_capabilities", [])
    )


def test_startup_stands_go2_before_navigation_initialization():
    config = json5.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    stand_up = next(
        hook for hook in config["lifecycle_hooks"] if hook["handler_config"].get("function") == "go2_stand_up_hook"
    )
    navigation = next(
        hook
        for hook in config["lifecycle_hooks"]
        if hook["handler_config"].get("function") == "start_autonomy_mid360_nav_hook"
    )

    assert stand_up["hook_type"] == "on_startup"
    assert stand_up["handler_type"] == "function"
    assert stand_up["handler_config"]["module_name"] == "go2_posture_hook"
    assert stand_up["handler_config"]["unitree_ethernet"] == "${UNITREE_ETHERNET:-eno1}"
    assert stand_up["handler_config"]["motion_mode"] == "Advanced"
    assert stand_up["handler_config"]["timeout_seconds"] == 5.0
    assert stand_up["timeout_seconds"] == 20
    assert stand_up["on_failure"] == "abort"
    assert stand_up["priority"] > navigation["priority"]


def test_no_arm_navigation_is_low_speed_real_robot_and_uses_local_map():
    config = json5.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    navigation = next(action for action in config["agent_actions"] if action["llm_label"] == "navigate_location")
    startup = next(
        hook["handler_config"]
        for hook in config["lifecycle_hooks"]
        if hook["handler_config"].get("function") == "start_autonomy_mid360_nav_hook"
    )
    shutdown = next(
        hook["handler_config"]
        for hook in config["lifecycle_hooks"]
        if hook["handler_config"].get("function") == "stop_autonomy_mid360_nav_hook"
    )

    assert navigation["config"]["allow_real_robot_goal"] is True
    assert navigation["config"]["stand_up_before_navigation"] is False
    assert startup["real_robot"] is True
    assert startup["max_speed"] == 0.05
    assert startup["max_yaw_rate"] == 10.0
    assert startup["auto_disarm_on_goal"] is True
    assert startup["use_livox_adapter"] is True
    assert shutdown["use_livox_adapter"] is True
    assert shutdown["session_adapter"] == startup["session_adapter"]
    assert "/livox/lidar" in startup["required_topics"]
    assert "/livox/imu" in startup["required_topics"]
    assert "/unitree/slam_lidar/points" in startup["required_topics"]
    assert "/unitree/slam_lidar/imu" not in startup["required_topics"]
    assert startup["required_publisher_topics"] == ["/livox/lidar", "/livox/imu"]
    assert startup["stop_container_on_shutdown"] is True
    assert shutdown["stop_container_on_shutdown"] is True
    assert Path(_expand(startup["host_map_file"])).is_file()


def test_no_arm_prompts_exist_and_state_capability_limit():
    config = json5.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    executor_prompt = Path(_expand(config["system_prompt_path"]))
    planner_prompt = Path(_expand(config["voice_task_planner_llm"]["config"]["system_prompt_path"]))

    assert executor_prompt.is_file()
    assert planner_prompt.is_file()
    assert "当前没有机械臂能力" in executor_prompt.read_text(encoding="utf-8")
    assert "没有机械臂" in planner_prompt.read_text(encoding="utf-8")


def test_no_arm_navigation_waits_for_robot_to_join_prior_vgraph_main_component():
    config = json5.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    startup = next(
        hook["handler_config"]
        for hook in config["lifecycle_hooks"]
        if hook["handler_config"].get("function") == "start_autonomy_mid360_nav_hook"
    )

    assert startup["load_prior_graph"] is True
    assert startup["guarded_readiness_timeout_seconds"] == 90.0
    assert startup["vgraph_readiness_check_enabled"] is True
    assert startup["vgraph_readiness_consecutive_samples"] == 3
    assert startup["vgraph_readiness_sample_interval_seconds"] == 1.0
    assert startup["vgraph_readiness_min_prior_component_ratio"] == 0.9
    assert startup["vgraph_readiness_max_robot_node_distance"] == 1.0


def test_no_arm_navigation_speaks_progress_only_during_goal_preparation():
    config = json5.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    navigation = next(action for action in config["agent_actions"] if action["llm_label"] == "navigate_location")
    feedback = navigation["config"]["progress_feedback"]

    assert feedback["action"] == "speak"
    assert feedback["delay_seconds"] > 0
    assert feedback["interval_seconds"] > 0
    assert feedback["wait_for_actions"] == ["speak"]
    assert feedback["random"] is True
    assert feedback["max_messages"] == 2
    assert len(feedback["messages"]) > feedback["max_messages"]
    assert all(message.strip() for message in feedback["messages"])


def test_fastlio_converts_only_lidar_and_uses_native_imu():
    parameters = yaml.safe_load(FASTLIO_CONFIG_PATH.read_text(encoding="utf-8"))["/**"]["ros__parameters"]
    assert parameters["common"]["lid_topic"] == "/unitree/slam_lidar/points"
    assert parameters["common"]["imu_topic"] == "/livox/imu"
    assert parameters["preprocess"]["timestamp_unit"] == 3
    assert parameters["preprocess"]["scan_rate"] == 20

    start_script = FASTLIO_START_PATH.read_text(encoding="utf-8")
    assert 'FASTLIO_IMU_TOPIC="${FASTLIO_IMU_TOPIC:-/livox/imu}"' in start_script
