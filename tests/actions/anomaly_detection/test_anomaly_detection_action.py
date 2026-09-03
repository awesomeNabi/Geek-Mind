import time
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from actions.anomaly_detection.connector.d435_openai import (
    AnomalyModelResult,
    D435OpenAIAnomalyConfig,
    D435OpenAIAnomalyConnector,
)
from actions.anomaly_detection.interface import AnomalyDetectionInput
from providers.inspection_workflow_provider import InspectionWorkflowProvider


class FakeD435Provider:
    def __init__(self, snapshot=None, running=True):
        self.snapshot = snapshot or {
            "color_image": np.zeros((8, 8, 3), dtype=np.uint8),
            "captured_at": time.time(),
        }
        self.running = running

    def realsense_running_for(self, camera_id):
        return self.running

    def get_realsense_snapshot(self, camera_id):
        return self.snapshot


@pytest.fixture
def workflow():
    provider = InspectionWorkflowProvider()
    provider.clear()
    yield provider
    provider.clear()


def make_connector(fake_d435, **config_overrides):
    config = D435OpenAIAnomalyConfig(api_key="test-key", retry_poll_interval_seconds=0.001, **config_overrides)
    with patch(
        "actions.anomaly_detection.connector.d435_openai.D435Provider",
        return_value=fake_d435,
    ):
        return D435OpenAIAnomalyConnector(config)


@pytest.mark.asyncio
async def test_confident_anomaly_is_published_and_recorded(workflow, monkeypatch):
    workflow.start("桌面巡检")
    connector = make_connector(FakeD435Provider())
    monkeypatch.setattr(
        connector,
        "_analyze",
        AsyncMock(
            return_value=AnomalyModelResult(
                observation="会议桌上有一个透明水瓶",
                is_anomaly=True,
                confidence=0.94,
                description="桌面上发现水瓶",
                objects=["透明水瓶"],
            )
        ),
    )

    await connector.connect(AnomalyDetectionInput("会议室"))

    status = workflow.snapshot()
    detection = status["latest_detection"]
    assert detection["status"] == "anomaly"
    assert detection["summary_recorded"] is True
    assert status["record_count"] == 1
    assert workflow.records()[0]["category"] == "anomaly_detection"


@pytest.mark.asyncio
async def test_low_confidence_uses_new_frame_and_second_result(workflow, monkeypatch):
    workflow.start("桌面巡检")
    first_snapshot = {
        "color_image": np.zeros((8, 8, 3), dtype=np.uint8),
        "captured_at": time.time(),
    }
    second_snapshot = {
        "color_image": np.ones((8, 8, 3), dtype=np.uint8),
        "captured_at": first_snapshot["captured_at"] + 0.1,
    }
    connector = make_connector(FakeD435Provider(first_snapshot))
    analyze = AsyncMock(
        side_effect=[
            AnomalyModelResult(
                observation="画面模糊",
                is_anomaly=False,
                confidence=0.3,
                description="无法看清台面",
                objects=[],
            ),
            AnomalyModelResult(
                observation="更新画面中台面为空",
                is_anomaly=False,
                confidence=0.9,
                description="台面整洁",
                objects=[],
            ),
        ]
    )
    monkeypatch.setattr(connector, "_analyze", analyze)
    monkeypatch.setattr(connector, "_wait_for_new_frame", AsyncMock(return_value=second_snapshot))

    await connector.connect(AnomalyDetectionInput("前台"))

    detection = workflow.snapshot()["latest_detection"]
    assert detection["status"] == "normal"
    assert detection["attempt_count"] == 2
    assert analyze.await_count == 2


@pytest.mark.asyncio
async def test_second_low_confidence_becomes_uncertain(workflow, monkeypatch):
    connector = make_connector(FakeD435Provider())
    low = AnomalyModelResult(
        observation="画面模糊",
        is_anomaly=False,
        confidence=0.2,
        description="看不清台面",
        objects=[],
    )
    monkeypatch.setattr(connector, "_analyze", AsyncMock(side_effect=[low, low]))
    monkeypatch.setattr(
        connector,
        "_wait_for_new_frame",
        AsyncMock(
            return_value={
                "color_image": np.ones((8, 8, 3), dtype=np.uint8),
                "captured_at": time.time() + 0.01,
            }
        ),
    )

    await connector.connect(AnomalyDetectionInput("茶水间"))

    detection = workflow.snapshot()["latest_detection"]
    assert detection["status"] == "uncertain"
    assert detection["is_anomaly"] is None
    assert detection["attempt_count"] == 2
    assert detection["summary_recorded"] is False


@pytest.mark.asyncio
async def test_no_new_retry_frame_becomes_uncertain(workflow, monkeypatch):
    connector = make_connector(FakeD435Provider())
    monkeypatch.setattr(
        connector,
        "_analyze",
        AsyncMock(
            return_value=AnomalyModelResult(
                observation="画面模糊",
                is_anomaly=False,
                confidence=0.4,
                description="无法确认",
                objects=[],
            )
        ),
    )
    monkeypatch.setattr(connector, "_wait_for_new_frame", AsyncMock(return_value=None))

    await connector.connect(AnomalyDetectionInput("走廊桌面"))

    detection = workflow.snapshot()["latest_detection"]
    assert detection["status"] == "uncertain"
    assert detection["attempt_count"] == 1
    assert "未取得更新画面" in detection["description"]


@pytest.mark.asyncio
async def test_camera_failure_is_structured_and_recorded(workflow):
    workflow.start("桌面巡检")
    connector = make_connector(FakeD435Provider(running=False))

    await connector.connect(AnomalyDetectionInput("会议室"))

    status = workflow.snapshot()
    detection = status["latest_detection"]
    assert detection["status"] == "failed"
    assert detection["error_code"] == "camera_unavailable"
    assert detection["summary_recorded"] is True
    assert status["record_count"] == 1


@pytest.mark.asyncio
async def test_invalid_model_response_is_structured(workflow, monkeypatch):
    connector = make_connector(FakeD435Provider())
    monkeypatch.setattr(connector, "_analyze", AsyncMock(side_effect=ValueError("invalid JSON response")))

    await connector.connect(AnomalyDetectionInput("前台"))

    detection = workflow.snapshot()["latest_detection"]
    assert detection["status"] == "failed"
    assert detection["error_code"] == "invalid_model_response"
