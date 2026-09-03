#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAGIC_DIR="${MAGIC_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
SESSION_NAME="${MAGIC_MINI_TMUX_SESSION:-magic_mini_humble}"
RUNTIME_DIR="${MAGIC_DIR}/.runtime"

usage() {
  cat <<EOF
Usage: $0 [start|start-agent|stop|restart|status|attach|check]

start        Mid360 driver + navigation container only (no MAGIC config/agent).
start-agent  Start MAGIC config in tmux (lifecycle hooks bring up FAST-LIO/nav).
             Run this separately when you need voice/LLM or publish_goal readiness
             via the config stack. Requires \`start\` infra first.

Default MAGIC_START_AGENT=false, so \`start\` does not launch run.py.
Set MAGIC_START_AGENT=true to restore the old combined start behavior.

Clear the area and keep the emergency stop ready before starting navigation.
EOF
}

load_env() {
  if [[ -f "${MAGIC_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${MAGIC_DIR}/.env"
    set +a
  fi

  export MAGIC_DIR
  export KOALA_FETCH_CONFIG="${KOALA_FETCH_CONFIG:-unitree_go2_koala_nav_vision_no_arm}"
  export UNITREE_ETHERNET="${UNITREE_ETHERNET:-eno1}"
  export CYCLONEDDS_INTERFACE="${CYCLONEDDS_INTERFACE:-${UNITREE_ETHERNET}}"
  export CYCLONEDDS_HOME="${CYCLONEDDS_HOME:-/home/nvidia/cyclonedds/install}"
  export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
  export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
  export MID360_ROS_DOMAIN_ID="${MID360_ROS_DOMAIN_ID:-${ROS_DOMAIN_ID}}"
  export MID360_MAPS_DIR="${MID360_MAPS_DIR:-${MAGIC_DIR}/service/unitree_native_slam}"
  export MID360_IMAGE="${MID360_IMAGE:-magic-mini-mid360-nav:humble}"
  export MID360_CONTAINER="${MID360_CONTAINER:-magic_mini_mid360_nav}"
  export MID360_RUNTIME="${MID360_RUNTIME:-docker}"
  export MID360_WORKSPACE_DIR="${MID360_WORKSPACE_DIR:-${MAGIC_DIR}/service/unitree_native_slam/autonomy_mid360}"
  export MID360_DRIVER_AUTOSTART="${MID360_DRIVER_AUTOSTART:-true}"
  export MID360_DRIVER_SESSION="${MID360_DRIVER_SESSION:-magic_mid360_driver}"
  export MID360_DRIVER_LOG="${MID360_DRIVER_LOG:-${RUNTIME_DIR}/mid360-driver.log}"
  export MID360_DRIVER_SCRIPT="${MID360_DRIVER_SCRIPT:-/home/nvidia/ws_mid360/scripts/start_mid360s.sh}"
  export MID360_DRIVER_SETUP="${MID360_DRIVER_SETUP:-/home/nvidia/ws_mid360/install/setup.bash}"
  export MID360_DRIVER_INTERFACE="${MID360_DRIVER_INTERFACE:-enx00e04c680d5f}"
  export MID360_DRIVER_HOST_IP="${MID360_DRIVER_HOST_IP:-192.168.200.1}"
  export MID360_LIDAR_IP="${MID360_LIDAR_IP:-192.168.200.20}"
  export MID360_DRIVER_TOPIC_TIMEOUT_SECONDS="${MID360_DRIVER_TOPIC_TIMEOUT_SECONDS:-20}"
  export MID360_RESET_NAVIGATION_ON_START="${MID360_RESET_NAVIGATION_ON_START:-true}"
  export MID360_STOP_DRIVER_WITH_STACK="${MID360_STOP_DRIVER_WITH_STACK:-true}"
  export MID360_STOP_CONTAINER_WITH_STACK="${MID360_STOP_CONTAINER_WITH_STACK:-true}"
  export MID360_SHUTDOWN_TIMEOUT_SECONDS="${MID360_SHUTDOWN_TIMEOUT_SECONDS:-45}"
  # Plan A default: infra only. Agent/config is started separately via start-agent.
  export MAGIC_START_AGENT="${MAGIC_START_AGENT:-false}"
  export REALSENSE_VERSION="${REALSENSE_VERSION:-2.57.7}"
  export REALSENSE_PREFIX="${REALSENSE_PREFIX:-${MAGIC_DIR}/.local/librealsense-${REALSENSE_VERSION}}"

  local python_version
  python_version="${REALSENSE_PYTHON_VERSION:-3.12}"
  export REALSENSE_PYTHONPATH="${REALSENSE_PYTHONPATH:-${REALSENSE_PREFIX}/lib/python${python_version}/site-packages}"
}

write_cyclonedds_config() {
  mkdir -p "${RUNTIME_DIR}"
  local config="${RUNTIME_DIR}/cyclonedds-${CYCLONEDDS_INTERFACE}.xml"
  cat >"${config}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<CycloneDDS xmlns="https://cdds.io/config">
  <Domain Id="any">
    <General>
      <Interfaces>
        <NetworkInterface name="${CYCLONEDDS_INTERFACE}" priority="default" multicast="default" />
      </Interfaces>
      <AllowMulticast>true</AllowMulticast>
    </General>
    <Discovery>
      <ParticipantIndex>auto</ParticipantIndex>
      <MaxAutoParticipantIndex>120</MaxAutoParticipantIndex>
    </Discovery>
  </Domain>
</CycloneDDS>
EOF
  export CYCLONEDDS_URI="file://${config}"
  export CYCLONEDDS_CONFIG_FILE="${config}"
}

require_file() {
  [[ -e "$1" ]] || { echo "Missing required file: $1" >&2; return 1; }
}

is_true() {
  case "${1,,}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

check_prerequisites() {
  local require_agent="${1:-false}"

  command -v tmux >/dev/null 2>&1 || { echo "tmux is not installed" >&2; return 1; }
  require_file /opt/ros/humble/setup.bash
  require_file "${MID360_MAPS_DIR}/aaa-fuck-magic-company_20260630_100336.pcd"
  require_file "${MAGIC_DIR}/service/unitree_native_slam/autonomy_mid360/prior_graphs/my_prior_graph_final.vgh"

  [[ "${UNITREE_ETHERNET}" == "eno1" ]] \
    || echo "WARNING: UNITREE_ETHERNET=${UNITREE_ETHERNET}; eno1 is the validated Go2 interface" >&2
  ip link show "${UNITREE_ETHERNET}" >/dev/null 2>&1 \
    || { echo "Network interface is missing: ${UNITREE_ETHERNET}" >&2; return 1; }
  [[ -f "${CYCLONEDDS_HOME}/lib/libddsc.so" || -f "${CYCLONEDDS_HOME}/lib/libddsc.so.0" ]] \
    || { echo "CycloneDDS library is missing below ${CYCLONEDDS_HOME}/lib" >&2; return 1; }

  if is_true "${require_agent}"; then
    command -v uv >/dev/null 2>&1 || { echo "uv is not installed" >&2; return 1; }
    require_file "${MAGIC_DIR}/.venv/bin/python"
    require_file "${MAGIC_DIR}/config/${KOALA_FETCH_CONFIG}.json5"
    [[ -n "${DASHSCOPE_API_KEY:-}" ]] \
      || { echo "DASHSCOPE_API_KEY is empty in ${MAGIC_DIR}/.env" >&2; return 1; }
    if [[ ! -d "${REALSENSE_PYTHONPATH}/pyrealsense2" ]]; then
      echo "WARNING: external pyrealsense2 is missing under ${REALSENSE_PYTHONPATH}" >&2
    fi
  fi

  if is_true "${MID360_DRIVER_AUTOSTART}"; then
    command -v ping >/dev/null 2>&1 || { echo "ping is not installed" >&2; return 1; }
    require_file "${MID360_DRIVER_SCRIPT}"
    require_file "${MID360_DRIVER_SETUP}"
    ip link show "${MID360_DRIVER_INTERFACE}" >/dev/null 2>&1 \
      || { echo "MID360 network interface is missing: ${MID360_DRIVER_INTERFACE}" >&2; return 1; }
    if ! ip -4 -o address show dev "${MID360_DRIVER_INTERFACE}" | grep -Fq " ${MID360_DRIVER_HOST_IP}/"; then
      echo "${MID360_DRIVER_INTERFACE} does not have ${MID360_DRIVER_HOST_IP}; configure the direct MID360 network first" >&2
      return 1
    fi
    if ! ping -c 1 -W 1 "${MID360_LIDAR_IP}" >/dev/null 2>&1; then
      echo "MID360 is not reachable at ${MID360_LIDAR_IP} via ${MID360_DRIVER_INTERFACE}" >&2
      return 1
    fi
  fi

  if [[ "${MID360_RUNTIME}" == "host" ]]; then
    require_file "${MID360_WORKSPACE_DIR}/install/setup.bash"
    return 0
  fi

  command -v docker >/dev/null 2>&1 || { echo "docker is not installed" >&2; return 1; }
  if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon is not accessible by ${USER}. Fix docker group/socket permissions first, or set MID360_RUNTIME=host in .env." >&2
    return 1
  fi
}

mid360_topic_has_data() {
  local topic="$1"
  local message_type="$2"
  local timeout_seconds="$3"

  timeout "${timeout_seconds}" env \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
    ROS_DOMAIN_ID="${MID360_ROS_DOMAIN_ID}" \
    ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY}" \
    ROS2CLI_NO_DAEMON=1 \
    CYCLONEDDS_URI="${CYCLONEDDS_URI}" \
    bash --noprofile --norc -c '
      set +u
      source "$1"
      source "$2"
      set -u
      ros2 topic echo --no-daemon "$3" "$4" --once >/dev/null
    ' _ /opt/ros/humble/setup.bash "${MID360_DRIVER_SETUP}" "${topic}" "${message_type}"
}

wait_for_mid360_data() {
  local topic
  local message_type
  for topic in /livox/lidar /livox/imu; do
    case "${topic}" in
      /livox/lidar) message_type="sensor_msgs/msg/PointCloud2" ;;
      /livox/imu) message_type="sensor_msgs/msg/Imu" ;;
    esac
    echo "Waiting for MID360 data on ${topic} ..."
    if ! mid360_topic_has_data "${topic}" "${message_type}" "${MID360_DRIVER_TOPIC_TIMEOUT_SECONDS}"; then
      echo "No message received on ${topic} within ${MID360_DRIVER_TOPIC_TIMEOUT_SECONDS}s" >&2
      return 1
    fi
  done
  echo "MID360 data ready: /livox/lidar and /livox/imu"
}

stop_named_session() {
  local session="$1"
  local grace_seconds="${2:-2}"
  if ! tmux has-session -t "${session}" 2>/dev/null; then
    return 0
  fi

  tmux send-keys -t "${session}:0" C-c 2>/dev/null || true
  sleep "${grace_seconds}"
  if tmux has-session -t "${session}" 2>/dev/null; then
    tmux kill-session -t "${session}"
  fi
}

start_mid360_driver() {
  if ! is_true "${MID360_DRIVER_AUTOSTART}"; then
    echo "MID360 driver autostart is disabled; expecting an external /livox publisher"
    return 0
  fi

  if tmux has-session -t "${MID360_DRIVER_SESSION}" 2>/dev/null; then
    if wait_for_mid360_data; then
      echo "Reusing MID360 driver session: ${MID360_DRIVER_SESSION}"
      return 0
    fi
    echo "Restarting stale MID360 driver session: ${MID360_DRIVER_SESSION}" >&2
    stop_named_session "${MID360_DRIVER_SESSION}" 2
  elif pgrep -f '[l]ivox_ros_driver2_node' >/dev/null 2>&1; then
    if wait_for_mid360_data; then
      echo "Reusing externally managed MID360 driver"
      return 0
    fi
    echo "A Livox driver process exists but is not publishing usable data; stop it before retrying" >&2
    return 1
  fi

  local driver_command
  : >"${MID360_DRIVER_LOG}"
  printf -v driver_command \
    'env RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=%q ROS_LOCALHOST_ONLY=%q CYCLONEDDS_URI=%q bash %q >>%q 2>&1' \
    "${MID360_ROS_DOMAIN_ID}" "${ROS_LOCALHOST_ONLY}" "${CYCLONEDDS_URI}" "${MID360_DRIVER_SCRIPT}" \
    "${MID360_DRIVER_LOG}"
  tmux new-session -d -s "${MID360_DRIVER_SESSION}" "${driver_command}"

  if ! wait_for_mid360_data; then
    echo "MID360 driver failed; recent output:" >&2
    tail -40 "${MID360_DRIVER_LOG}" >&2 || true
    stop_named_session "${MID360_DRIVER_SESSION}" 2
    return 1
  fi
}

stop_mid360_driver() {
  if ! is_true "${MID360_STOP_DRIVER_WITH_STACK}"; then
    return 0
  fi
  if tmux has-session -t "${MID360_DRIVER_SESSION}" 2>/dev/null; then
    echo "Stopping MID360 driver session: ${MID360_DRIVER_SESSION}"
    stop_named_session "${MID360_DRIVER_SESSION}" 3
  fi
}

stop_navigation_container() {
  if [[ "${MID360_RUNTIME}" == "host" ]] || ! is_true "${MID360_STOP_CONTAINER_WITH_STACK}"; then
    return 0
  fi
  if [[ "$(docker inspect -f '{{.State.Running}}' "${MID360_CONTAINER}" 2>/dev/null || true)" == "true" ]]; then
    echo "Stopping navigation container: ${MID360_CONTAINER}"
    docker stop -t 15 "${MID360_CONTAINER}" >/dev/null
  fi
}

cleanup_navigation_runtime() {
  local session
  # Stop Docker first so an in-flight lifecycle startup cannot recreate a tmux
  # shell after its docker exec command returns.
  stop_navigation_container
  for session in go2_mid360_autonomy_nav go2_fastlio_autonomy go2_livox_compat; do
    stop_named_session "${session}" 2
  done
  sleep 0.5
  for session in go2_mid360_autonomy_nav go2_fastlio_autonomy go2_livox_compat; do
    stop_named_session "${session}" 0
  done
}

ensure_navigation_runtime() {
  if [[ "${MID360_RUNTIME}" == "host" ]]; then
    require_file "${MID360_WORKSPACE_DIR}/install/setup.bash"
    echo "Mid360 navigation runtime: host ROS 2 Humble (${MID360_WORKSPACE_DIR})"
    return 0
  fi

  IMAGE_NAME="${MID360_IMAGE}" \
  CONTAINER_NAME="${MID360_CONTAINER}" \
  MAPS_DIR="${MID360_MAPS_DIR}" \
  MID360_ROS_DOMAIN_ID="${MID360_ROS_DOMAIN_ID}" \
  CYCLONEDDS_CONFIG_FILE="${CYCLONEDDS_CONFIG_FILE}" \
  bash "${MAGIC_DIR}/service/unitree_native_slam/autonomy_mid360/scripts/run_container.sh"
}

run_runtime() {
  load_env
  write_cyclonedds_config

  # ROS 2 Humble uses Python 3.10. The MAGIC runtime uses uv Python 3.12 and
  # communicates through CycloneDDS directly, so do not leak ROS Python paths.
  unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION
  unset PYTHONHOME
  export PYTHONPATH="${REALSENSE_PYTHONPATH}"
  export LD_LIBRARY_PATH="${CYCLONEDDS_HOME}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
  export NO_PROXY="${NO_PROXY:-127.0.0.1,localhost,192.168.1.0/24,192.168.123.0/24}"
  export no_proxy="${no_proxy:-${NO_PROXY}}"
  unset http_proxy HTTP_PROXY https_proxy HTTPS_PROXY ALL_PROXY all_proxy

  cd "${MAGIC_DIR}"
  exec uv run --no-sync --extra dds --extra wake-word src/run.py "${KOALA_FETCH_CONFIG}"
}

start_infrastructure() {
  local require_agent=false
  if is_true "${MAGIC_START_AGENT}"; then
    require_agent=true
  fi
  check_prerequisites "${require_agent}"
  if is_true "${MID360_RESET_NAVIGATION_ON_START}"; then
    cleanup_navigation_runtime
  fi
  start_mid360_driver
  ensure_navigation_runtime
}

start_agent_session() {
  if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    echo "Agent session already running: ${SESSION_NAME}"
    return 0
  fi
  check_prerequisites true
  if [[ "$(docker inspect -f '{{.State.Running}}' "${MID360_CONTAINER}" 2>/dev/null || true)" != "true" ]] \
    && [[ "${MID360_RUNTIME}" != "host" ]]; then
    echo "Navigation container is not running. Run \`$0 start\` first." >&2
    return 1
  fi
  tmux new-session -d -s "${SESSION_NAME}" \
    "bash --noprofile --norc -lc 'exec $(printf '%q' "$0") _run'"
  echo "Started agent ${SESSION_NAME} with config ${KOALA_FETCH_CONFIG}; attach with: $0 attach"
  echo "Note: lifecycle hooks start FAST-LIO/nav; publish_goal works after hooks finish."
}

start_stack() {
  if is_true "${MAGIC_START_AGENT}" && tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    echo "Session already running: ${SESSION_NAME}"
    return 0
  fi
  start_infrastructure
  if is_true "${MAGIC_START_AGENT}"; then
    start_agent_session
  else
    echo "Started Mid360 driver + navigation container only (MAGIC agent not started)."
    echo "Start config/agent separately with: $0 start-agent"
    echo "Or: cd ${MAGIC_DIR} && uv run --no-sync --extra dds --extra wake-word src/run.py ${KOALA_FETCH_CONFIG}"
    echo "publish_goal requires the agent lifecycle hooks (or an equivalent nav launch) to be running."
  fi
}

stop_stack() {
  if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    tmux send-keys -t "${SESSION_NAME}:0" C-c
    local waited=0
    while tmux has-session -t "${SESSION_NAME}" 2>/dev/null; do
      if (( waited >= MID360_SHUTDOWN_TIMEOUT_SECONDS * 2 )); then
        echo "Runtime did not stop within ${MID360_SHUTDOWN_TIMEOUT_SECONDS}s; terminating tmux session" >&2
        tmux kill-session -t "${SESSION_NAME}"
        break
      fi
      sleep 0.5
      ((waited += 1))
    done
  else
    echo "Runtime session is not running: ${SESSION_NAME}"
  fi

  cleanup_navigation_runtime
  stop_mid360_driver
  echo "Stopped MAGIC, navigation, and managed MID360 services"
}

show_status() {
  if tmux has-session -t "${SESSION_NAME}" 2>/dev/null; then
    echo "runtime: running (${SESSION_NAME})"
  else
    echo "runtime: stopped (${SESSION_NAME})"
  fi
  if tmux has-session -t "${MID360_DRIVER_SESSION}" 2>/dev/null; then
    echo "MID360 driver: running (${MID360_DRIVER_SESSION})"
  elif pgrep -f '[l]ivox_ros_driver2_node' >/dev/null 2>&1; then
    echo "MID360 driver: running (external process)"
  else
    echo "MID360 driver: stopped"
  fi
  if [[ "${MID360_RUNTIME}" == "host" ]]; then
    if [[ -f "${MID360_WORKSPACE_DIR}/install/setup.bash" ]]; then
      echo "navigation runtime: host (${MID360_WORKSPACE_DIR})"
    else
      echo "navigation runtime: host workspace missing (${MID360_WORKSPACE_DIR})"
    fi
  else
    docker inspect -f 'navigation container: {{.State.Status}}' "${MID360_CONTAINER}" 2>/dev/null \
      || echo "navigation container: missing or inaccessible"
  fi
  for session in go2_livox_compat go2_fastlio_autonomy go2_mid360_autonomy_nav; do
    if tmux has-session -t "${session}" 2>/dev/null; then
      echo "${session}: running"
    else
      echo "${session}: stopped"
    fi
  done
}

load_env
write_cyclonedds_config

case "${1:-start}" in
  start) start_stack ;;
  start-agent) start_agent_session ;;
  stop) stop_stack ;;
  restart)
    stop_stack
    start_stack
    ;;
  status) show_status ;;
  attach) exec tmux attach-session -t "${SESSION_NAME}" ;;
  check)
    check_prerequisites true
    echo "Humble runtime prerequisites passed"
    ;;
  _run) run_runtime ;;
  -h|--help|help) usage ;;
  *)
    usage >&2
    exit 2
    ;;
esac
