import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

from actions.base import ActionConfig, ActionConnector, AgentAction, Interface
from actions.orchestrator import ActionOrchestrator
from llm.output_model import Action


@dataclass
class _TestInput:
    action: str


@dataclass
class _TestInterface(Interface[_TestInput, _TestInput]):
    input: _TestInput
    output: _TestInput


class _ControlledConnector(ActionConnector[ActionConfig, _TestInput]):
    def __init__(self, config: ActionConfig):
        super().__init__(config)
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def connect(self, output_interface: _TestInput) -> None:
        self.started.set()
        await self.release.wait()


class _RecordingConnector(ActionConnector[ActionConfig, _TestInput]):
    def __init__(self, config: ActionConfig):
        super().__init__(config)
        self.messages: list[str] = []
        self.initial_release = asyncio.Event()
        self.initial_started = asyncio.Event()

    async def connect(self, output_interface: _TestInput) -> None:
        if output_interface.action == "initial":
            self.initial_started.set()
            await self.initial_release.wait()
        self.messages.append(output_interface.action)


def _orchestrator(delay_seconds: float = 0.0):
    navigation_connector = _ControlledConnector(
        ActionConfig(
            progress_feedback={
                "action": "speak",
                "delay_seconds": delay_seconds,
                "interval_seconds": 60.0,
                "wait_for_actions": ["speak"],
                "messages": ["thinking", "still thinking"],
            }
        )
    )
    speak_connector = _RecordingConnector(ActionConfig())
    config = SimpleNamespace(
        agent_actions=[
            AgentAction("speak", "speak", _TestInterface, speak_connector, False),
            AgentAction("navigate_location", "navigate_location", _TestInterface, navigation_connector, False),
        ],
        action_execution_mode="concurrent",
        action_dependencies={},
        action_gate=None,
    )
    return ActionOrchestrator(config), navigation_connector, speak_connector


async def _wait_for(predicate, timeout: float = 0.5) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0)


def test_progress_feedback_waits_for_initial_speech_and_stops_with_source_action():
    async def run_test() -> None:
        orchestrator, navigation, speak = _orchestrator()
        await orchestrator.promise(
            [
                Action(type="speak", value="initial"),
                Action(type="navigate_location", value="warehouse"),
            ]
        )

        await navigation.started.wait()
        await speak.initial_started.wait()
        await asyncio.sleep(0)
        assert speak.messages == []

        speak.initial_release.set()
        await _wait_for(lambda: speak.messages == ["initial", "thinking"])

        navigation.release.set()
        await orchestrator.flush_promises()
        assert speak.messages == ["initial", "thinking"]

    asyncio.run(run_test())


def test_progress_feedback_is_not_sent_when_source_finishes_before_delay():
    async def run_test() -> None:
        orchestrator, navigation, speak = _orchestrator(delay_seconds=0.05)
        await orchestrator.promise([Action(type="navigate_location", value="warehouse")])

        await navigation.started.wait()
        navigation.release.set()
        await orchestrator.flush_promises()
        assert speak.messages == []

    asyncio.run(run_test())


def test_select_progress_feedback_messages_random_subset():
    pool = ["a", "b", "c", "d"]
    selected = ActionOrchestrator._select_progress_feedback_messages(
        pool,
        randomize=True,
        max_messages=2,
    )
    assert len(selected) == 2
    assert len(set(selected)) == 2
    assert set(selected).issubset(set(pool))


def test_select_progress_feedback_messages_keeps_order_without_random():
    pool = ["a", "b", "c", "d"]
    selected = ActionOrchestrator._select_progress_feedback_messages(
        pool,
        randomize=False,
        max_messages=2,
    )
    assert selected == ["a", "b"]
