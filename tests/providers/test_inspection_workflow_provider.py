import pytest

from providers.inspection_workflow_provider import (
    InspectionWorkflowProvider,
    InspectionWorkflowStateError,
)


@pytest.fixture
def workflow():
    provider = InspectionWorkflowProvider()
    provider.clear()
    yield provider
    provider.clear()


def test_workflow_lifecycle_and_duplicate_finalize(workflow):
    started = workflow.start("办公区巡检")
    assert started["state"] == "running"
    assert started["record_count"] == 0

    workflow.record("机器人已到达会议室", category="navigation")
    _, recorded = workflow.publish_detection(
        {
            "status": "anomaly",
            "location": "会议室",
            "description": "桌面上发现水瓶",
        },
        "会议室：发现异常，桌面上发现水瓶。",
    )
    assert recorded is True
    assert len(workflow.records()) == 2

    preparation = workflow.prepare_finalize("")
    assert preparation.already_finalized is False
    assert len(preparation.records) == 2

    completed = workflow.complete_finalize(preparation.generation, "巡检完成，会议室发现水瓶。", source="model")
    assert completed["state"] == "completed"
    assert completed["summary_source"] == "model"
    assert completed["speech_status"] == "pending"

    spoken = workflow.mark_speech(preparation.generation, "spoken")
    assert spoken["speech_status"] == "spoken"

    duplicate = workflow.prepare_finalize("")
    assert duplicate.already_finalized is True
    assert duplicate.final_summary == "巡检完成，会议室发现水瓶。"


def test_record_requires_running_workflow(workflow):
    with pytest.raises(InspectionWorkflowStateError, match="workflow is idle"):
        workflow.record("不应被记录")


def test_stale_finalize_cannot_overwrite_new_workflow(workflow):
    workflow.start("旧任务")
    preparation = workflow.prepare_finalize("")
    workflow.start("新任务")

    with pytest.raises(InspectionWorkflowStateError, match="workflow changed"):
        workflow.complete_finalize(preparation.generation, "旧总结", source="model")


def test_detection_without_active_workflow_is_not_recorded(workflow):
    snapshot, recorded = workflow.publish_detection(
        {
            "status": "normal",
            "location": "前台",
            "description": "台面整洁",
        },
        "前台：未发现异常。",
    )

    assert recorded is False
    assert snapshot["latest_detection"]["summary_recorded"] is False
    assert snapshot["record_count"] == 0


def test_detection_from_old_generation_does_not_pollute_new_workflow(workflow):
    old = workflow.start("旧任务")
    workflow.start("新任务")

    snapshot, recorded = workflow.publish_detection(
        {
            "status": "anomaly",
            "location": "旧位置",
            "description": "旧任务检测结果",
        },
        "旧位置：发现异常。",
        expected_generation=old["generation"],
    )

    assert recorded is False
    assert snapshot["record_count"] == 0
    assert snapshot["latest_detection"]["summary_record_skipped_reason"] == "workflow_changed"
