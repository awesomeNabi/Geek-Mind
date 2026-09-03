from pathlib import Path
import subprocess
from unittest.mock import Mock, patch

import pytest

from hooks.autonomy_mid360_nav_hook import (
    AutonomyMid360NavHookContext,
    _ensure_adapter_session,
    _ensure_fastlio_session,
    _load_prior_graph,
    _publish_navigation_boundary,
    _start_autonomy_mid360_nav,
    _stop_autonomy_mid360_nav,
    _wait_for_guarded_navigation_ready,
    _wait_for_required_topics,
    _wait_for_vgraph_readiness,
)

REQUIRED_TOPIC_OUTPUT = "\n".join(
    [
        "/Odometry_loc",
        "/cloud_registered_1",
        "/state_estimation",
        "/registered_scan",
        "/map",
        "/localization_3d_confidence",
        "/baselink2map",
        "/odom2map",
        "/goal_point",
        "/way_point",
        "/way_point_global",
        "/cmd_vel",
        "/far_reach_goal_status",
        "/robot_vgraph",
        "/reset_visibility_graph",
    ]
)


def test_start_autonomy_mid360_nav_starts_fastlio_and_nav_sessions():
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        result = Mock()
        result.returncode = 1 if args[:3] == ["tmux", "has-session", "-t"] else 0
        if args[:3] == ["docker", "inspect", "-f"]:
            result.stdout = "true\n"
        elif args[:4] == ["docker", "exec", "-i", "magic_mini_mid360_nav"]:
            result.stdout = REQUIRED_TOPIC_OUTPUT
        return result

    ctx = AutonomyMid360NavHookContext(
        base_dir="/home/unitree/MAGIC_MINI/service/unitree_native_slam/autonomy_mid360",
        map_file="/workspace/maps/autonomy_go2_mid360_test_20260609_150606.pcd",
        host_map_file="/home/unitree/maps/autonomy_go2_mid360_test_20260609_150606.pcd",
        wait_seconds=0.0,
        auto_start_fastlio_mapping_delay_seconds=0.0,
        real_robot=False,
        route_planner=True,
        global_localization=True,
    )

    with (
        patch.object(Path, "exists", return_value=True),
        patch("hooks.autonomy_mid360_nav_hook.subprocess.run", side_effect=fake_run),
    ):
        result = _start_autonomy_mid360_nav(ctx)

    assert result["status"] == "success"
    fastlio_session = next(
        call for call in calls if call[:5] == ["tmux", "new-session", "-d", "-s", "go2_fastlio_autonomy"]
    )
    nav_session = next(
        call for call in calls if call[:5] == ["tmux", "new-session", "-d", "-s", "go2_mid360_autonomy_nav"]
    )
    fastlio_start_key = next(call for call in calls if call == ["tmux", "send-keys", "-t", "go2_fastlio_autonomy", "s"])

    assert "bash --noprofile --norc -lc" in fastlio_session[5]
    assert "start_fastlio_unitree_autonomy_for_nav.sh" in fastlio_session[5]
    assert "--no-foxglove" in fastlio_session[5]
    assert fastlio_start_key
    nav_command = nav_session[5]
    assert "bash --noprofile --norc -lc" in nav_command
    assert "--no-real-robot" in nav_command
    assert "--route-planner" in nav_command
    assert "--global-localization" in nav_command
    assert "--no-foxglove" in nav_command
    assert "--no-rviz" in nav_command
    assert "--autonomy-mode" in nav_command
    assert "--auto-initialpose" in nav_command
    assert "--sensor-offset-x 0.187" in nav_command
    assert "--map-file /workspace/maps/autonomy_go2_mid360_test_20260609_150606.pcd" in nav_command


def test_start_autonomy_mid360_nav_can_start_real_robot_with_auto_disarm():
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        result = Mock()
        result.returncode = 1 if args[:3] == ["tmux", "has-session", "-t"] else 0
        if args[:3] == ["docker", "inspect", "-f"]:
            result.stdout = "true\n"
        elif args[:4] == ["docker", "exec", "-i", "magic_mini_mid360_nav"]:
            result.stdout = REQUIRED_TOPIC_OUTPUT
        return result

    ctx = AutonomyMid360NavHookContext(
        wait_seconds=0.0,
        auto_start_fastlio_mapping_delay_seconds=0.0,
        real_robot=True,
        auto_disarm_on_goal=True,
        max_speed=0.1,
    )

    with (
        patch.object(Path, "exists", return_value=True),
        patch("hooks.autonomy_mid360_nav_hook.subprocess.run", side_effect=fake_run),
    ):
        _start_autonomy_mid360_nav(ctx)

    nav_session = next(
        call for call in calls if call[:5] == ["tmux", "new-session", "-d", "-s", "go2_mid360_autonomy_nav"]
    )
    nav_command = nav_session[5]
    assert "--real-robot" in nav_command
    assert "--auto-disarm-on-goal" in nav_command
    assert "--auto-disarm-stop-count 20" in nav_command
    assert "--max-speed 0.1" in nav_command


def test_fastlio_start_key_failure_cleans_up_new_session():
    ctx = AutonomyMid360NavHookContext(
        auto_start_fastlio_mapping_delay_seconds=0.0,
        session_stop_grace_seconds=0.0,
    )

    with (
        patch("hooks.autonomy_mid360_nav_hook._session_exists", return_value=False),
        patch("hooks.autonomy_mid360_nav_hook._require_path"),
        patch("hooks.autonomy_mid360_nav_hook._new_session"),
        patch("hooks.autonomy_mid360_nav_hook._send_key", side_effect=RuntimeError("tmux input failed")),
        patch("hooks.autonomy_mid360_nav_hook._stop_session_gracefully") as mock_stop,
        pytest.raises(RuntimeError, match="tmux input failed"),
    ):
        _ensure_fastlio_session(ctx)

    mock_stop.assert_called_once_with(ctx.session_fastlio, 0.0)


def test_livox_adapter_session_uses_humble_container_entrypoint():
    ctx = AutonomyMid360NavHookContext(
        base_dir="/home/nvidia/MAGIC_MINI/service/unitree_native_slam/autonomy_mid360",
        container_name="magic_mini_mid360_nav",
        use_livox_adapter=True,
    )

    with (
        patch("hooks.autonomy_mid360_nav_hook._session_exists", return_value=False),
        patch("hooks.autonomy_mid360_nav_hook._require_path"),
        patch("hooks.autonomy_mid360_nav_hook._new_session") as mock_new_session,
    ):
        assert _ensure_adapter_session(ctx) is True

    session, command = mock_new_session.call_args.args
    assert session == "go2_livox_compat"
    assert "start_livox_compat_adapter.sh" in command
    assert "CONTAINER_NAME=magic_mini_mid360_nav" in command


def test_start_autonomy_mid360_nav_fails_when_required_topics_are_missing():
    def fake_run(args, **kwargs):
        result = Mock()
        result.returncode = 1 if args[:3] == ["tmux", "has-session", "-t"] else 0
        result.stdout = ""
        if args[:3] == ["docker", "inspect", "-f"]:
            result.stdout = "true\n"
        elif args[:4] == ["docker", "exec", "-i", "magic_mini_mid360_nav"]:
            result.stdout = "/Odometry_loc\n"
        return result

    ctx = AutonomyMid360NavHookContext(
        wait_seconds=0.0,
        auto_start_fastlio_mapping_delay_seconds=0.0,
        health_check_timeout_seconds=0.0,
        health_check_interval_seconds=0.0,
    )

    with (
        patch.object(Path, "exists", return_value=True),
        patch("hooks.autonomy_mid360_nav_hook.subprocess.run", side_effect=fake_run),
        pytest.raises(RuntimeError, match="missing topics"),
    ):
        _start_autonomy_mid360_nav(ctx)


def test_start_autonomy_mid360_nav_retries_topic_list_timeout_as_missing_topics():
    def fake_run(args, **kwargs):
        if args[:4] == ["docker", "exec", "-i", "magic_mini_mid360_nav"] and "ros2 topic list" in args[-1]:
            raise subprocess.TimeoutExpired(args, timeout=8)

        result = Mock()
        result.returncode = 1 if args[:3] == ["tmux", "has-session", "-t"] else 0
        result.stdout = ""
        if args[:3] == ["docker", "inspect", "-f"]:
            result.stdout = "true\n"
        return result

    ctx = AutonomyMid360NavHookContext(
        wait_seconds=0.0,
        auto_start_fastlio_mapping_delay_seconds=0.0,
        health_check_timeout_seconds=0.0,
        health_check_interval_seconds=0.0,
    )

    with (
        patch.object(Path, "exists", return_value=True),
        patch("hooks.autonomy_mid360_nav_hook.subprocess.run", side_effect=fake_run),
        pytest.raises(RuntimeError, match="missing topics"),
    ):
        _start_autonomy_mid360_nav(ctx)


def test_required_publisher_topic_rejects_subscriber_only_topic():
    ctx = AutonomyMid360NavHookContext(
        required_topics=["/livox/lidar"],
        required_publisher_topics=["/livox/lidar"],
        health_check_timeout_seconds=0.0,
        health_check_interval_seconds=0.0,
    )

    with (
        patch("hooks.autonomy_mid360_nav_hook._list_ros_topics", return_value={"/livox/lidar"}),
        patch("hooks.autonomy_mid360_nav_hook._topic_endpoint_count", return_value=0),
        pytest.raises(RuntimeError, match="topics without publishers: /livox/lidar"),
    ):
        _wait_for_required_topics(ctx)


def test_required_publisher_topic_accepts_live_publisher_endpoint():
    ctx = AutonomyMid360NavHookContext(
        required_topics=["/livox/lidar"],
        required_publisher_topics=["/livox/lidar"],
        health_check_timeout_seconds=0.0,
        health_check_interval_seconds=0.0,
    )

    with (
        patch("hooks.autonomy_mid360_nav_hook._list_ros_topics", return_value={"/livox/lidar"}),
        patch("hooks.autonomy_mid360_nav_hook._topic_endpoint_count", return_value=1),
    ):
        _wait_for_required_topics(ctx)


def test_guarded_readiness_waits_for_vgraph_connectivity_after_basic_checks():
    ctx = AutonomyMid360NavHookContext(
        load_prior_graph=True,
        prior_graph_file="/workspace/prior_graph.vgh",
        guarded_readiness_timeout_seconds=30.0,
    )

    with (
        patch("hooks.autonomy_mid360_nav_hook._guarded_navigation_ready", return_value=(True, "")),
        patch("hooks.autonomy_mid360_nav_hook._wait_for_vgraph_readiness") as mock_vgraph_ready,
    ):
        _wait_for_guarded_navigation_ready(ctx)

    mock_vgraph_ready.assert_called_once()
    assert 0 < mock_vgraph_ready.call_args.args[1] <= 30.0


def test_guarded_readiness_skips_vgraph_connectivity_without_prior_graph():
    ctx = AutonomyMid360NavHookContext(load_prior_graph=False, guarded_readiness_timeout_seconds=30.0)

    with (
        patch("hooks.autonomy_mid360_nav_hook._guarded_navigation_ready", return_value=(True, "")),
        patch("hooks.autonomy_mid360_nav_hook._wait_for_vgraph_readiness") as mock_vgraph_ready,
    ):
        _wait_for_guarded_navigation_ready(ctx)

    mock_vgraph_ready.assert_not_called()


def test_vgraph_readiness_runs_read_only_probe_with_configured_thresholds():
    ctx = AutonomyMid360NavHookContext(
        load_prior_graph=True,
        prior_graph_file="/workspace/prior_graph.vgh",
        vgraph_readiness_consecutive_samples=4,
        vgraph_readiness_sample_interval_seconds=1.5,
        vgraph_readiness_min_prior_component_ratio=0.85,
        vgraph_readiness_max_robot_node_distance=0.8,
    )
    result = Mock(returncode=0, stdout="V-Graph ready\n", stderr="")

    with patch("hooks.autonomy_mid360_nav_hook._run_ros_command", return_value=result) as mock_run:
        _wait_for_vgraph_readiness(ctx, 25.0)

    command = mock_run.call_args.args[1]
    assert "check_vgraph_ready.py" in command
    assert "--prior-graph /workspace/prior_graph.vgh" in command
    assert "--consecutive-samples 4" in command
    assert "--sample-interval 1.5" in command
    assert "--min-prior-component-ratio 0.85" in command
    assert "--max-robot-node-distance 0.8" in command
    assert mock_run.call_args.kwargs["timeout"] == 30.0


def test_vgraph_readiness_surfaces_connectivity_timeout_details():
    ctx = AutonomyMid360NavHookContext(load_prior_graph=True, prior_graph_file="/workspace/prior_graph.vgh")
    result = Mock(
        returncode=1,
        stdout="",
        stderr="ERROR: largest nearby component has 25 nodes; requires at least 413",
    )

    with (
        patch("hooks.autonomy_mid360_nav_hook._run_ros_command", return_value=result),
        pytest.raises(RuntimeError, match="largest nearby component has 25 nodes"),
    ):
        _wait_for_vgraph_readiness(ctx, 10.0)


def test_start_autonomy_mid360_nav_rolls_back_sessions_created_by_failed_start():
    ctx = AutonomyMid360NavHookContext(
        stop_existing_sessions=False,
        wait_seconds=0.0,
        health_check_enabled=True,
        session_stop_grace_seconds=0.0,
    )

    with (
        patch("hooks.autonomy_mid360_nav_hook._require_tmux"),
        patch("hooks.autonomy_mid360_nav_hook._require_container"),
        patch("hooks.autonomy_mid360_nav_hook._require_path"),
        patch("hooks.autonomy_mid360_nav_hook._require_container_file"),
        patch("hooks.autonomy_mid360_nav_hook._ensure_fastlio_session", return_value=True),
        patch("hooks.autonomy_mid360_nav_hook._ensure_nav_session", return_value=True),
        patch("hooks.autonomy_mid360_nav_hook._wait_for_required_topics", side_effect=RuntimeError("not ready")),
        patch("hooks.autonomy_mid360_nav_hook._stop_session_gracefully") as mock_stop,
        pytest.raises(RuntimeError, match="not ready"),
    ):
        _start_autonomy_mid360_nav(ctx)

    assert [call.args[0] for call in mock_stop.call_args_list] == [ctx.session_nav, ctx.session_fastlio]


def test_start_autonomy_mid360_nav_loads_graph_then_publishes_boundary():
    events = []
    ctx = AutonomyMid360NavHookContext(
        load_prior_graph=True,
        prior_graph_file="/workspace/prior_graph.vgh",
        navigation_boundary_enabled=True,
        navigation_boundary_points=[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0]],
        wait_seconds=10.0,
        stop_existing_sessions=False,
    )

    with (
        patch("hooks.autonomy_mid360_nav_hook._require_tmux"),
        patch("hooks.autonomy_mid360_nav_hook._require_container"),
        patch("hooks.autonomy_mid360_nav_hook._require_path"),
        patch("hooks.autonomy_mid360_nav_hook._require_container_file"),
        patch(
            "hooks.autonomy_mid360_nav_hook._ensure_fastlio_session",
            side_effect=lambda _: events.append("fastlio") or True,
        ),
        patch(
            "hooks.autonomy_mid360_nav_hook.time.sleep", side_effect=lambda seconds: events.append(f"wait:{seconds}")
        ),
        patch("hooks.autonomy_mid360_nav_hook._ensure_nav_session", side_effect=lambda _: events.append("nav") or True),
        patch(
            "hooks.autonomy_mid360_nav_hook._wait_for_required_topics", side_effect=lambda _: events.append("health")
        ),
        patch("hooks.autonomy_mid360_nav_hook._load_prior_graph", side_effect=lambda _: events.append("prior_graph")),
        patch(
            "hooks.autonomy_mid360_nav_hook._wait_for_guarded_navigation_ready",
            side_effect=lambda _: events.append("guarded_ready"),
        ),
        patch(
            "hooks.autonomy_mid360_nav_hook._publish_navigation_boundary",
            side_effect=lambda _: events.append("boundary"),
        ),
    ):
        _start_autonomy_mid360_nav(ctx)

    assert events == [
        "fastlio",
        "wait:10.0",
        "nav",
        "health",
        "prior_graph",
        "guarded_ready",
        "boundary",
    ]


def test_load_prior_graph_waits_for_nonempty_decoded_graph():
    ctx = AutonomyMid360NavHookContext(
        load_prior_graph=True,
        prior_graph_file="/workspace/prior_graph.vgh",
        prior_graph_wait_seconds=20.0,
    )
    result = Mock(returncode=0, stdout="Decoded prior graph size: 599\n", stderr="")

    with patch("hooks.autonomy_mid360_nav_hook.subprocess.run", return_value=result) as mock_run:
        _load_prior_graph(ctx)

    command = mock_run.call_args.args[0]
    assert command[:5] == ["docker", "exec", "-i", "magic_mini_mid360_nav", "bash"]
    assert "/workspace/prior_graph.vgh" in command
    loader_script = mock_run.call_args.kwargs["input"]
    assert 'ros2 topic echo --once "${verify_topic}" --field size' in loader_script
    assert "ros2 topic pub --once /read_file_dir" in loader_script
    assert "far_planner is not subscribed" in loader_script
    assert "Node name: far_planner(_node)?" in loader_script
    assert loader_script.index("Node name: far_planner") < loader_script.index("topic echo --once")
    assert loader_script.index("topic echo --once") < loader_script.index("topic pub --once")
    assert "awk '/^[[:space:]]*[0-9]+" in loader_script
    syntax_check = subprocess.run(["bash", "-n"], input=loader_script, text=True, capture_output=True, check=False)
    assert syntax_check.returncode == 0, syntax_check.stderr


def test_load_prior_graph_fails_when_decoder_rejects_graph():
    ctx = AutonomyMid360NavHookContext(load_prior_graph=True, prior_graph_file="/workspace/prior_graph.vgh")
    result = Mock(returncode=1, stdout="", stderr="ERROR: decoded prior graph size is 0")

    with (
        patch("hooks.autonomy_mid360_nav_hook.subprocess.run", return_value=result),
        pytest.raises(RuntimeError, match="decoded prior graph size is 0"),
    ):
        _load_prior_graph(ctx)


def test_publish_navigation_boundary_uses_company_points_without_preserve_z():
    ctx = AutonomyMid360NavHookContext(
        navigation_boundary_enabled=True,
        navigation_boundary_points=[[1.0, 2.0, 0.1], [3.0, 4.0, 0.2], [5.0, 6.0, 0.3]],
    )
    result = Mock(returncode=0, stdout="published\n", stderr="")

    with (
        patch("hooks.autonomy_mid360_nav_hook._topic_endpoint_count", return_value=1),
        patch("hooks.autonomy_mid360_nav_hook.subprocess.run", return_value=result) as mock_run,
    ):
        _publish_navigation_boundary(ctx)

    command = mock_run.call_args.args[0]
    assert "--frame" in command and command[command.index("--frame") + 1] == "map"
    assert command[command.index("--points") + 1] == "1.0,2.0,0.1;3.0,4.0,0.2;5.0,6.0,0.3"
    assert command[command.index("--output-z") + 1] == "0.0"
    assert "--preserve-z" not in command


def test_publish_navigation_boundary_requires_local_planner_subscriber():
    ctx = AutonomyMid360NavHookContext(
        navigation_boundary_enabled=True,
        navigation_boundary_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]],
    )

    with (
        patch("hooks.autonomy_mid360_nav_hook._topic_endpoint_count", return_value=0),
        patch("hooks.autonomy_mid360_nav_hook.subprocess.run") as mock_run,
        pytest.raises(RuntimeError, match="localPlanner is not subscribed"),
    ):
        _publish_navigation_boundary(ctx)

    mock_run.assert_not_called()


def test_stop_autonomy_mid360_nav_stops_configured_container_after_sessions():
    ctx = AutonomyMid360NavHookContext(stop_container_on_shutdown=True, session_stop_grace_seconds=0.0)

    with (
        patch("hooks.autonomy_mid360_nav_hook._stop_robot_motion") as mock_stop_motion,
        patch("hooks.autonomy_mid360_nav_hook._stop_session_gracefully") as mock_stop_session,
        patch("hooks.autonomy_mid360_nav_hook._stop_container") as mock_stop_container,
        patch("hooks.autonomy_mid360_nav_hook._is_host_runtime", return_value=False),
    ):
        result = _stop_autonomy_mid360_nav(ctx)

    assert result["status"] == "success"
    mock_stop_motion.assert_called_once_with(ctx)
    assert [call.args[0] for call in mock_stop_session.call_args_list] == [ctx.session_nav, ctx.session_fastlio]
    mock_stop_container.assert_called_once_with(ctx.container_name)


def test_stop_autonomy_mid360_nav_does_not_stop_docker_for_host_runtime():
    ctx = AutonomyMid360NavHookContext(stop_container_on_shutdown=True, session_stop_grace_seconds=0.0)

    with (
        patch("hooks.autonomy_mid360_nav_hook._stop_robot_motion"),
        patch("hooks.autonomy_mid360_nav_hook._stop_session_gracefully"),
        patch("hooks.autonomy_mid360_nav_hook._stop_container") as mock_stop_container,
        patch("hooks.autonomy_mid360_nav_hook._is_host_runtime", return_value=True),
    ):
        _stop_autonomy_mid360_nav(ctx)

    mock_stop_container.assert_not_called()
