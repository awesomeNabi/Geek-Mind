from pathlib import Path

import json5

from runtime.cortex import ModeCortexRuntime


ROOT = Path(__file__).resolve().parents[2]
DETECTION_CONFIG = ROOT / "config" / "detection.json5"


def test_detection_config_uses_one_mode_and_plain_sub_voices():
    raw = json5.loads(DETECTION_CONFIG.read_text(encoding="utf-8"))

    assert "modes" not in raw
    assert "default_mode" not in raw
    assert "emit_step_modes" not in raw["voice_task_planner"]

    planner_prompt = raw["voice_task_planner_llm"]["config"]["system_prompt"]
    assert "task_plan" not in planner_prompt
    assert '"mode"' not in planner_prompt
    assert '"sub_voices"' in planner_prompt


def test_inspection_steps_are_not_inferred_as_navigation_from_location_names():
    runtime = ModeCortexRuntime.__new__(ModeCortexRuntime)

    one_turn_steps = [
        "开始巡检：前台和吧台台面巡检",
        "台面异常检测：前台",
        "台面异常检测：吧台",
        "结束巡检并播报总结",
        "请用户说明需要巡检的点位",
    ]
    for step in one_turn_steps:
        assert runtime._infer_voice_task_subtask_mode(step) == "welcome"

    assert runtime._infer_voice_task_subtask_mode("导航到前台") == "nav"
    assert runtime._infer_voice_task_subtask_mode("导航到吧台") == "nav"
