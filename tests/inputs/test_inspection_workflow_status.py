import json

import pytest

from actions import load_action
from inputs import load_input
from inputs.plugins.inspection_workflow_status import (
    InspectionWorkflowStatus,
    InspectionWorkflowStatusConfig,
)
from llm.function_schemas import generate_function_schema_from_action
from providers.inspection_workflow_provider import InspectionWorkflowProvider


@pytest.fixture
def workflow():
    provider = InspectionWorkflowProvider()
    provider.clear()
    yield provider
    provider.clear()


@pytest.mark.asyncio
async def test_status_input_emits_each_revision_once(workflow):
    sensor = InspectionWorkflowStatus(InspectionWorkflowStatusConfig(poll_interval_seconds=0.001))

    initial = await sensor._poll()
    assert json.loads(initial)["state"] == "idle"
    assert await sensor._poll() is None

    workflow.start("巡检")
    updated = await sensor._poll()
    assert json.loads(updated)["state"] == "running"
    await sensor.raw_to_text(updated)
    block = sensor.formatted_latest_buffer()
    assert "INPUT: InspectionWorkflowStatus" in block
    assert '"state": "running"' in block
    assert sensor.formatted_latest_buffer() is None


def test_input_plugin_can_be_discovered(workflow):
    sensor = load_input(
        {
            "type": "InspectionWorkflowStatus",
            "config": {"poll_interval_seconds": 0.01},
        }
    )
    assert isinstance(sensor, InspectionWorkflowStatus)


def test_new_actions_load_and_generate_function_schemas(workflow):
    summary = load_action(
        {
            "name": "summary",
            "llm_label": "summary",
            "connector": "openai_qwen",
            "config": {"tts_enabled": False},
        }
    )
    summary_schema = generate_function_schema_from_action(summary)
    assert summary_schema["function"]["name"] == "summary"
    assert summary_schema["function"]["parameters"]["properties"]["operation"]["enum"] == [
        "start",
        "record",
        "finalize",
    ]

    with patch_d435_provider():
        anomaly = load_action(
            {
                "name": "anomaly_detection",
                "llm_label": "anomaly_detection",
                "connector": "d435_openai",
                "config": {"api_key": "test-key"},
            }
        )
    anomaly_schema = generate_function_schema_from_action(anomaly)
    assert anomaly_schema["function"]["name"] == "anomaly_detection"
    assert list(anomaly_schema["function"]["parameters"]["properties"]) == ["location"]


def patch_d435_provider():
    from unittest.mock import patch

    return patch(
        "actions.anomaly_detection.connector.d435_openai.D435Provider",
        return_value=object(),
    )
