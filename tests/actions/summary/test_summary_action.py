from unittest.mock import AsyncMock

import pytest

from actions.summary.connector.openai_qwen import (
    SummaryOpenAIQwenConfig,
    SummaryOpenAIQwenConnector,
)
from actions.summary.interface import SummaryInput, SummaryOperation
from providers.inspection_workflow_provider import InspectionWorkflowProvider


@pytest.fixture
def workflow():
    provider = InspectionWorkflowProvider()
    provider.clear()
    yield provider
    provider.clear()


@pytest.fixture
def connector(workflow):
    return SummaryOpenAIQwenConnector(
        SummaryOpenAIQwenConfig(
            api_key="test-key",
            tts_enabled=False,
        )
    )


@pytest.mark.asyncio
async def test_summary_start_record_finalize_and_dedupe(connector, workflow, monkeypatch):
    generate = AsyncMock(return_value="办公区巡检完成，会议室未发现异常。")
    monkeypatch.setattr(connector, "_generate_summary", generate)

    await connector.connect(SummaryInput(SummaryOperation.START, "办公区巡检"))
    await connector.connect(SummaryInput(SummaryOperation.RECORD, "已到达会议室"))
    await connector.connect(SummaryInput(SummaryOperation.FINALIZE, ""))

    status = workflow.snapshot()
    assert status["state"] == "completed"
    assert status["final_summary"] == "办公区巡检完成，会议室未发现异常。"
    assert status["summary_source"] == "model"
    assert status["speech_status"] == "disabled"
    assert generate.await_count == 1

    await connector.connect(SummaryInput(SummaryOperation.FINALIZE, ""))
    assert generate.await_count == 1


@pytest.mark.asyncio
async def test_summary_model_failure_uses_fallback(connector, workflow, monkeypatch):
    monkeypatch.setattr(connector, "_generate_summary", AsyncMock(side_effect=RuntimeError("offline")))

    await connector.connect(SummaryInput(SummaryOperation.START, "桌面巡检"))
    await connector.connect(SummaryInput(SummaryOperation.RECORD, "前台台面正常"))
    await connector.connect(SummaryInput(SummaryOperation.FINALIZE, ""))

    status = workflow.snapshot()
    assert status["state"] == "completed"
    assert status["summary_source"] == "fallback"
    assert "前台台面正常" in status["final_summary"]


@pytest.mark.asyncio
async def test_summary_speech_failure_is_visible(workflow, monkeypatch):
    connector = SummaryOpenAIQwenConnector(SummaryOpenAIQwenConfig(api_key="test-key", tts_enabled=True))
    monkeypatch.setattr(connector, "_generate_summary", AsyncMock(return_value="巡检完成。"))
    monkeypatch.setattr(connector, "_speak_summary", AsyncMock(side_effect=RuntimeError("speaker offline")))

    await connector.connect(SummaryInput(SummaryOperation.START, "巡检"))
    await connector.connect(SummaryInput(SummaryOperation.FINALIZE, ""))

    status = workflow.snapshot()
    assert status["state"] == "completed"
    assert status["speech_status"] == "speech_failed"
    assert status["error"]["code"] == "speech_failed"


@pytest.mark.asyncio
async def test_invalid_summary_record_publishes_error(connector, workflow):
    await connector.connect(SummaryInput(SummaryOperation.RECORD, "没有活动任务"))

    status = workflow.snapshot()
    assert status["state"] == "idle"
    assert status["error"]["source"] == "summary"
    assert status["error"]["code"] == "invalid_operation"


@pytest.mark.asyncio
async def test_old_speech_completion_does_not_overwrite_new_workflow(workflow, monkeypatch):
    connector = SummaryOpenAIQwenConnector(SummaryOpenAIQwenConfig(api_key="test-key", tts_enabled=True))
    monkeypatch.setattr(connector, "_generate_summary", AsyncMock(return_value="旧任务完成。"))

    async def start_new_workflow(_summary):
        workflow.start("新任务")

    monkeypatch.setattr(connector, "_speak_summary", start_new_workflow)
    await connector.connect(SummaryInput(SummaryOperation.START, "旧任务"))
    await connector.connect(SummaryInput(SummaryOperation.FINALIZE, ""))

    status = workflow.snapshot()
    assert status["title"] == "新任务"
    assert status["state"] == "running"
    assert status["speech_status"] == "idle"
