import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from actions.navigate_location.connector.autonomy_mid360_nav import (
    AutonomyMid360NavConfig,
    AutonomyMid360NavConnector,
)
from actions.navigate_location.interface import NavigateLocationInput


class TestAutonomyMid360NavConnector:
    @pytest.fixture
    def nav_connector(self, tmp_path):
        locations_file = tmp_path / "locations.json"
        goal_script = tmp_path / "publish_goal.sh"
        goal_script.write_text("#!/usr/bin/env bash\n")
        locations_file.write_text(
            json.dumps(
                {
                    "吧台": [
                        [1.0, 2.0, 0.0, 0.0, 0.0, 0.0, 1.0],
                        [3.0, 4.0, 0.5, 0.0, 0.0, 0.0, 1.0],
                    ],
                    "office": {
                        "pose": {
                            "position": {"x": 5.0, "y": 6.0, "z": 0.1},
                            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                        }
                    },
                    "empty": [],
                },
                ensure_ascii=False,
            )
        )
        config = AutonomyMid360NavConfig(
            locations_file=str(locations_file),
            container_name="magic_mini_mid360_nav",
            goal_script=str(goal_script),
            workspace_setup="/opt/unitree_native_slam/install/setup.bash",
            goal_wait_seconds=7.0,
            timeout_seconds=60.0,
        )
        return AutonomyMid360NavConnector(config)

    def test_connect_publishes_last_pose_as_goal_point(self, nav_connector):
        process = Mock()
        process.communicate = AsyncMock(return_value=(b"published", b""))
        process.returncode = 0

        with (
            patch.object(nav_connector, "_container_running", return_value=True),
            patch(
                "actions.navigate_location.connector.autonomy_mid360_nav.asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=process),
            ) as mock_exec,
            patch.object(nav_connector, "_monitor_arrival", new=AsyncMock()),
            patch.object(nav_connector.io_provider, "add_dynamic_variable") as mock_var,
        ):
            asyncio.run(nav_connector.connect(NavigateLocationInput(action="去吧台")))

        command = mock_exec.call_args.args
        assert command[:5] == (
            "env",
            "MID360_RUNTIME=docker",
            "CONTAINER_NAME=magic_mini_mid360_nav",
            "WORKSPACE_DIR=/opt/unitree_native_slam",
            "bash",
        )
        assert "--reset-graph" not in command
        assert "--real-robot-ok" not in command
        assert command[-7:] == ("--frame", "map", "--wait", "7.0", "3.0", "4.0", "0.5")
        mock_var.assert_called_with(
            "autonomy_navigation_status",
            {
                "navigation_status": "executing",
                "target_location": "吧台",
                "message": "autonomy navigation goal accepted by planner",
                "updated_at": mock_var.call_args.args[1]["updated_at"],
            },
        )

    def test_connect_accepts_pose_dict_format(self, nav_connector):
        process = Mock()
        process.communicate = AsyncMock(return_value=(b"published", b""))
        process.returncode = 0

        with (
            patch.object(nav_connector, "_container_running", return_value=True),
            patch(
                "actions.navigate_location.connector.autonomy_mid360_nav.asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=process),
            ) as mock_exec,
            patch.object(nav_connector, "_monitor_arrival", new=AsyncMock()),
        ):
            asyncio.run(nav_connector.connect(NavigateLocationInput(action="navigate to office")))

        command = mock_exec.call_args.args
        assert command[-3:] == ("5.0", "6.0", "0.1")

    def test_connect_stands_up_before_publishing_goal_when_enabled(self, nav_connector):
        nav_connector.config.stand_up_before_navigation = True
        process = Mock()
        process.communicate = AsyncMock(return_value=(b"published", b""))
        process.returncode = 0

        with (
            patch.object(nav_connector, "_container_running", return_value=True),
            patch.object(
                nav_connector,
                "_stand_up_before_navigation",
                new=AsyncMock(return_value=True),
            ) as mock_stand_up,
            patch(
                "actions.navigate_location.connector.autonomy_mid360_nav.asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=process),
            ) as mock_exec,
            patch.object(nav_connector, "_monitor_arrival", new=AsyncMock()),
        ):
            asyncio.run(nav_connector.connect(NavigateLocationInput(action="吧台")))

        mock_stand_up.assert_awaited_once_with("吧台")
        mock_exec.assert_awaited_once()

    def test_connect_does_not_publish_goal_when_stand_up_fails(self, nav_connector):
        nav_connector.config.stand_up_before_navigation = True

        with (
            patch.object(nav_connector, "_container_running", return_value=True),
            patch.object(
                nav_connector,
                "_stand_up_before_navigation",
                new=AsyncMock(return_value=False),
            ) as mock_stand_up,
            patch(
                "actions.navigate_location.connector.autonomy_mid360_nav.asyncio.create_subprocess_exec",
                new=AsyncMock(),
            ) as mock_exec,
        ):
            asyncio.run(nav_connector.connect(NavigateLocationInput(action="吧台")))

        mock_stand_up.assert_awaited_once_with("吧台")
        mock_exec.assert_not_awaited()

    def test_stand_up_uses_configured_unitree_interface(self, nav_connector):
        nav_connector.config.stand_up_before_navigation = True
        nav_connector.config.unitree_ethernet = "enp2s0"
        nav_connector.config.stand_up_timeout_seconds = 7.0

        with patch(
            "hooks.go2_posture_hook.go2_stand_up_hook",
            new=AsyncMock(),
        ) as mock_stand_up:
            result = asyncio.run(nav_connector._stand_up_before_navigation("吧台"))

        assert result is True
        mock_stand_up.assert_awaited_once_with(
            {
                "unitree_ethernet": "enp2s0",
                "timeout_seconds": 7.0,
                "from_mode": "",
                "pre_stand_up_delay_seconds": 0.0,
            }
        )

    def test_stand_up_failure_publishes_failed_navigation_status(self, nav_connector):
        nav_connector.config.stand_up_before_navigation = True

        with (
            patch(
                "hooks.go2_posture_hook.go2_stand_up_hook",
                new=AsyncMock(side_effect=RuntimeError("sport service unavailable")),
            ),
            patch.object(nav_connector.io_provider, "add_dynamic_variable") as mock_var,
        ):
            result = asyncio.run(nav_connector._stand_up_before_navigation("吧台"))

        assert result is False
        assert mock_var.call_args.args[1]["navigation_status"] == "failed"
        assert mock_var.call_args.args[1]["target_location"] == "吧台"
        assert mock_var.call_args.args[1]["message"] == ("stand up before navigation failed: sport service unavailable")

    def test_build_goal_command_can_request_graph_reset(self, nav_connector):
        nav_connector.config.reset_graph_before_goal = True

        command = nav_connector._build_goal_command([1.0, 2.0, 3.0])

        assert "--reset-graph" in command

    def test_connect_reports_active_goal_as_busy(self, nav_connector):
        process = Mock()
        process.communicate = AsyncMock(return_value=(b"", b"ERROR: Active /way_point_global detected"))
        process.returncode = 3

        with (
            patch.object(nav_connector, "_container_running", return_value=True),
            patch(
                "actions.navigate_location.connector.autonomy_mid360_nav.asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=process),
            ),
            patch.object(nav_connector.io_provider, "add_dynamic_variable") as mock_var,
        ):
            asyncio.run(nav_connector.connect(NavigateLocationInput(action="吧台")))

        assert mock_var.call_args.args[1]["navigation_status"] == "busy"
        assert "Active /way_point_global detected" in mock_var.call_args.args[1]["message"]

    def test_connect_terminates_guarded_goal_process_on_timeout(self, nav_connector):
        process = Mock()
        process.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        process.returncode = None
        process.wait = AsyncMock(return_value=0)

        with (
            patch.object(nav_connector, "_container_running", return_value=True),
            patch(
                "actions.navigate_location.connector.autonomy_mid360_nav.asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=process),
            ),
            patch.object(nav_connector.io_provider, "add_dynamic_variable") as mock_var,
        ):
            asyncio.run(nav_connector.connect(NavigateLocationInput(action="吧台")))

        process.terminate.assert_called_once()
        assert mock_var.call_args.args[1]["navigation_status"] == "failed"
        assert "timed out" in mock_var.call_args.args[1]["message"]

    def test_connect_missing_location_does_not_publish(self, nav_connector):
        with (
            patch.object(nav_connector, "_container_running", return_value=True),
            patch(
                "actions.navigate_location.connector.autonomy_mid360_nav.asyncio.create_subprocess_exec",
                new=AsyncMock(),
            ) as mock_exec,
            patch.object(nav_connector.io_provider, "add_dynamic_variable") as mock_var,
        ):
            asyncio.run(nav_connector.connect(NavigateLocationInput(action="会议室")))

        mock_exec.assert_not_called()
        mock_var.assert_called_with(
            "autonomy_navigation_status",
            {
                "navigation_status": "failed",
                "target_location": "会议室",
                "message": "location '会议室' not found",
                "updated_at": mock_var.call_args.args[1]["updated_at"],
            },
        )

    def test_connect_empty_location_does_not_publish(self, nav_connector):
        with (
            patch.object(nav_connector, "_container_running", return_value=True),
            patch(
                "actions.navigate_location.connector.autonomy_mid360_nav.asyncio.create_subprocess_exec",
                new=AsyncMock(),
            ) as mock_exec,
            patch.object(nav_connector.io_provider, "add_dynamic_variable") as mock_var,
        ):
            asyncio.run(nav_connector.connect(NavigateLocationInput(action="empty")))

        mock_exec.assert_not_called()
        assert mock_var.call_args.args[1]["navigation_status"] == "failed"

    def test_connect_blocks_when_container_is_not_running(self, nav_connector):
        with (
            patch.object(nav_connector, "_container_running", return_value=False),
            patch(
                "actions.navigate_location.connector.autonomy_mid360_nav.asyncio.create_subprocess_exec",
                new=AsyncMock(),
            ) as mock_exec,
            patch.object(nav_connector.io_provider, "add_dynamic_variable") as mock_var,
        ):
            asyncio.run(nav_connector.connect(NavigateLocationInput(action="吧台")))

        mock_exec.assert_not_called()
        assert mock_var.call_args.args[1]["message"] == "container is not running: magic_mini_mid360_nav"

    def test_arrival_monitor_publishes_arrived_status(self, nav_connector):
        process = Mock()
        process.stdout = Mock()
        process.stdout.readline = AsyncMock(side_effect=[b"data: false\n", b"data: true\n"])
        process.returncode = None
        process.wait = AsyncMock(return_value=0)

        with (
            patch(
                "actions.navigate_location.connector.autonomy_mid360_nav.asyncio.create_subprocess_exec",
                new=AsyncMock(return_value=process),
            ),
            patch.object(nav_connector.io_provider, "add_dynamic_variable") as mock_var,
        ):
            asyncio.run(nav_connector._monitor_arrival("吧台"))

        assert mock_var.call_args.args[1]["navigation_status"] == "arrived"
        process.terminate.assert_called_once()
