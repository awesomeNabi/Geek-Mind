#!/usr/bin/env bash

set -u

SESSION_NAME="${KOALA_FETCH_TMUX_SESSION:-magic_mini_stack}"
MAGIC_DIR="${MAGIC_DIR:-/home/unitree/MAGIC_MINI}"
ARX_ROS2_SCRIPT="${ARX_ROS2_SCRIPT:-/home/unitree/unitree_sdk2_python/scripts_v2/start_arx_ros2.sh}"
ROS_DOMAIN_ID_VALUE="${ROS_DOMAIN_ID:-231}"
ROS_LOCALHOST_ONLY_VALUE="${ROS_LOCALHOST_ONLY:-0}"
UNITREE_ETHERNET_VALUE="${UNITREE_ETHERNET:-eth0}"
ASR_MICROPHONE_NAME_VALUE="${ASR_MICROPHONE_NAME:-pulse}"
ASR_ALSA_CARD_VALUE="${ASR_ALSA_CARD:-MINI}"
DASHSCOPE_CHAT_MODEL_VALUE="${DASHSCOPE_CHAT_MODEL:-deepseek-v4-pro}"
KOALA_FETCH_CONFIG_VALUE="${KOALA_FETCH_CONFIG:-unitree_go2_koala_fetch_single_mode}"
MID360_CONFIG_NAME="unitree_go2_koala_fetch_single_mode_autonomy_mid360"
MID360_SERVICE_DIR="${MAGIC_DIR}/service/unitree_native_slam/autonomy_mid360"
SHERPA_ONNX_KWS_MODEL_DIR_VALUE="${SHERPA_ONNX_KWS_MODEL_DIR:-${MAGIC_DIR}/service/models/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01}"
SHERPA_ONNX_KWS_ENCODER_VALUE="${SHERPA_ONNX_KWS_ENCODER:-${SHERPA_ONNX_KWS_MODEL_DIR_VALUE}/encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx}"
SHERPA_ONNX_KWS_DECODER_VALUE="${SHERPA_ONNX_KWS_DECODER:-${SHERPA_ONNX_KWS_MODEL_DIR_VALUE}/decoder-epoch-12-avg-2-chunk-16-left-64.onnx}"
SHERPA_ONNX_KWS_JOINER_VALUE="${SHERPA_ONNX_KWS_JOINER:-${SHERPA_ONNX_KWS_MODEL_DIR_VALUE}/joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx}"
SHERPA_ONNX_KWS_TOKENS_VALUE="${SHERPA_ONNX_KWS_TOKENS:-${SHERPA_ONNX_KWS_MODEL_DIR_VALUE}/tokens.txt}"
SHERPA_ONNX_KWS_KEYWORDS_FILE_VALUE="${SHERPA_ONNX_KWS_KEYWORDS_FILE:-${SHERPA_ONNX_KWS_MODEL_DIR_VALUE}/keywords.txt}"
NO_PROXY_VALUE="${KOALA_NO_PROXY:-127.0.0.1,localhost,127.0.0.1:5000,127.0.0.1:6793,192.168.1.112}"
CYCLONEDDS_ARX_CONFIG="${CYCLONEDDS_ARX_CONFIG:-/tmp/cyclonedds_arx_lo.xml}"
CYCLONEDDS_HOME_VALUE="${CYCLONEDDS_HOME:-/home/unitree/cyclonedds_ws/install/cyclonedds}"

usage() {
  cat <<EOF
Usage: $0 [start|stop|restart|status|attach]

Environment overrides:
  KOALA_FETCH_TMUX_SESSION  default: ${SESSION_NAME}
  KOALA_FETCH_CONFIG        default: ${KOALA_FETCH_CONFIG_VALUE}
  MID360_ROS_DOMAIN_ID      default: 0 (Mid360 Docker service only)
  DASHSCOPE_API_KEY         required, or set it in ${MAGIC_DIR}/.env
  SHERPA_ONNX_KWS_MODEL_DIR default: ${SHERPA_ONNX_KWS_MODEL_DIR_VALUE}
  SHERPA_ONNX_KWS_ENCODER   default: model-dir encoder int8 chunk-16
  SHERPA_ONNX_KWS_DECODER   default: model-dir decoder chunk-16
  SHERPA_ONNX_KWS_JOINER    default: model-dir joiner int8 chunk-16
  SHERPA_ONNX_KWS_TOKENS    default: model-dir tokens.txt
  SHERPA_ONNX_KWS_KEYWORDS_FILE default: model-dir keywords.txt
  UNITREE_ETHERNET          default: ${UNITREE_ETHERNET_VALUE}
  ROS_DOMAIN_ID             default: ${ROS_DOMAIN_ID_VALUE}
  ROS_LOCALHOST_ONLY        default: ${ROS_LOCALHOST_ONLY_VALUE}
EOF
}

load_env_file() {
  if [ -f "${MAGIC_DIR}/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "${MAGIC_DIR}/.env"
    set +a
  fi
}

resolve_env_values() {
  ROS_DOMAIN_ID_VALUE="${ROS_DOMAIN_ID:-231}"
  ROS_LOCALHOST_ONLY_VALUE="${ROS_LOCALHOST_ONLY:-0}"
  CYCLONEDDS_HOME_VALUE="${CYCLONEDDS_HOME:-/home/unitree/cyclonedds_ws/install/cyclonedds}"
  UNITREE_ETHERNET_VALUE="${UNITREE_ETHERNET:-eth0}"
  ASR_MICROPHONE_NAME_VALUE="${ASR_MICROPHONE_NAME:-pulse}"
  ASR_ALSA_CARD_VALUE="${ASR_ALSA_CARD:-MINI}"
  DASHSCOPE_CHAT_MODEL_VALUE="${DASHSCOPE_CHAT_MODEL:-deepseek-v4-pro}"
  KOALA_FETCH_CONFIG_VALUE="${KOALA_FETCH_CONFIG:-unitree_go2_koala_fetch_single_mode}"
  SHERPA_ONNX_KWS_MODEL_DIR_VALUE="${SHERPA_ONNX_KWS_MODEL_DIR:-${MAGIC_DIR}/service/models/sherpa-onnx-kws-zipformer-wenetspeech-3.3M-2024-01-01}"
  SHERPA_ONNX_KWS_ENCODER_VALUE="${SHERPA_ONNX_KWS_ENCODER:-${SHERPA_ONNX_KWS_MODEL_DIR_VALUE}/encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx}"
  SHERPA_ONNX_KWS_DECODER_VALUE="${SHERPA_ONNX_KWS_DECODER:-${SHERPA_ONNX_KWS_MODEL_DIR_VALUE}/decoder-epoch-12-avg-2-chunk-16-left-64.onnx}"
  SHERPA_ONNX_KWS_JOINER_VALUE="${SHERPA_ONNX_KWS_JOINER:-${SHERPA_ONNX_KWS_MODEL_DIR_VALUE}/joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx}"
  SHERPA_ONNX_KWS_TOKENS_VALUE="${SHERPA_ONNX_KWS_TOKENS:-${SHERPA_ONNX_KWS_MODEL_DIR_VALUE}/tokens.txt}"
  SHERPA_ONNX_KWS_KEYWORDS_FILE_VALUE="${SHERPA_ONNX_KWS_KEYWORDS_FILE:-${SHERPA_ONNX_KWS_MODEL_DIR_VALUE}/keywords.txt}"
  NO_PROXY_VALUE="${KOALA_NO_PROXY:-127.0.0.1,localhost,127.0.0.1:5000,127.0.0.1:6793,192.168.1.112}"
}

require_file() {
  local path="$1"
  if [ ! -e "${path}" ]; then
    echo "Missing required file: ${path}" >&2
    exit 1
  fi
}

require_command() {
  local name="$1"
  if ! command -v "${name}" >/dev/null 2>&1; then
    echo "Missing required command: ${name}" >&2
    exit 1
  fi
}

ensure_prerequisites() {
  require_command tmux
  require_command amixer
  require_command uv
  require_file "${ARX_ROS2_SCRIPT}"
  require_file /opt/ros/foxy/setup.bash
  require_file /home/unitree/ARX_X5/ROS2/X5_ws/install/local_setup.bash
  require_file /home/unitree/ARX_X5/ROS2/X5_ws/install/setup.bash
  require_file /home/unitree/cyclonedds_ws/install/setup.bash
  require_file "${CYCLONEDDS_HOME_VALUE}/lib/libddsc.so"
  require_file /home/unitree/OM1-ros2-sdk/install/setup.bash
  require_file "${MAGIC_DIR}/system_hw_test/arx_x5_motion_zenoh_bridge.py"
  require_file "${MAGIC_DIR}/src/run.py"

  case "${KOALA_FETCH_CONFIG_VALUE}" in
    ""|*[!A-Za-z0-9_-]*)
      echo "Invalid KOALA_FETCH_CONFIG: ${KOALA_FETCH_CONFIG_VALUE}" >&2
      exit 1
      ;;
  esac
  require_file "${MAGIC_DIR}/config/${KOALA_FETCH_CONFIG_VALUE}.json5"

  if [ "${KOALA_FETCH_CONFIG_VALUE}" = "${MID360_CONFIG_NAME}" ]; then
    require_command docker
    require_file "${MID360_SERVICE_DIR}/scripts/run_container.sh"
    require_file "${MID360_SERVICE_DIR}/scripts/start_fastlio_unitree_autonomy_for_nav.sh"
    require_file "${MID360_SERVICE_DIR}/scripts/start_nav.sh"
    require_file "${MID360_SERVICE_DIR}/scripts/publish_goal.sh"
    require_file "${MID360_SERVICE_DIR}/prior_graphs/my_prior_graph_final.vgh"
    require_file /unitree/module/unitree_slam/bin/mid360_driver
    require_file /home/unitree/maps/aaa-fuck-magic-company_20260630_100336.pcd
  fi

  if [ -z "${DASHSCOPE_API_KEY:-}" ]; then
    echo "DASHSCOPE_API_KEY is not set. Export it first or put it in ${MAGIC_DIR}/.env." >&2
    exit 1
  fi
  if [ -z "${SHERPA_ONNX_KWS_ENCODER_VALUE}" ]; then
    echo "SHERPA_ONNX_KWS_ENCODER is not set. Export it first or put it in ${MAGIC_DIR}/.env." >&2
    exit 1
  fi
  if [ -z "${SHERPA_ONNX_KWS_DECODER_VALUE}" ]; then
    echo "SHERPA_ONNX_KWS_DECODER is not set. Export it first or put it in ${MAGIC_DIR}/.env." >&2
    exit 1
  fi
  if [ -z "${SHERPA_ONNX_KWS_JOINER_VALUE}" ]; then
    echo "SHERPA_ONNX_KWS_JOINER is not set. Export it first or put it in ${MAGIC_DIR}/.env." >&2
    exit 1
  fi
  if [ -z "${SHERPA_ONNX_KWS_TOKENS_VALUE}" ]; then
    echo "SHERPA_ONNX_KWS_TOKENS is not set. Export it first or put it in ${MAGIC_DIR}/.env." >&2
    exit 1
  fi
  if [ -z "${SHERPA_ONNX_KWS_KEYWORDS_FILE_VALUE}" ]; then
    echo "SHERPA_ONNX_KWS_KEYWORDS_FILE is not set. Export it first or put it in ${MAGIC_DIR}/.env." >&2
    exit 1
  fi
  require_file "${SHERPA_ONNX_KWS_ENCODER_VALUE}"
  require_file "${SHERPA_ONNX_KWS_DECODER_VALUE}"
  require_file "${SHERPA_ONNX_KWS_JOINER_VALUE}"
  require_file "${SHERPA_ONNX_KWS_TOKENS_VALUE}"
  require_file "${SHERPA_ONNX_KWS_KEYWORDS_FILE_VALUE}"
}

ensure_navigation_service() {
  if [ "${KOALA_FETCH_CONFIG_VALUE}" != "${MID360_CONFIG_NAME}" ]; then
    return
  fi

  echo "Ensuring portable Mid360 navigation container is running..."
  MID360_ROS_DOMAIN_ID="${MID360_ROS_DOMAIN_ID:-0}" \
    bash "${MID360_SERVICE_DIR}/scripts/run_container.sh"
}

tmux_has_session() {
  tmux has-session -t "${SESSION_NAME}" >/dev/null 2>&1
}

send_line() {
  local window="$1"
  local line="$2"
  tmux send-keys -t "${SESSION_NAME}:${window}" "${line}" C-m
}

create_cyclonedds_config() {
  cat >"${CYCLONEDDS_ARX_CONFIG}" <<'EOF'
<CycloneDDS>
  <Domain>
    <General>
      <AllowMulticast>true</AllowMulticast>
    </General>
  </Domain>
</CycloneDDS>
EOF
}

set_tmux_environment() {
  tmux set-environment -t "${SESSION_NAME}" DASHSCOPE_API_KEY "${DASHSCOPE_API_KEY}"
  tmux set-environment -t "${SESSION_NAME}" UNITREE_ETHERNET "${UNITREE_ETHERNET_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" ASR_MICROPHONE_NAME "${ASR_MICROPHONE_NAME_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" ASR_ALSA_CARD "${ASR_ALSA_CARD_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" DASHSCOPE_CHAT_MODEL "${DASHSCOPE_CHAT_MODEL_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" KOALA_FETCH_CONFIG "${KOALA_FETCH_CONFIG_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" SHERPA_ONNX_KWS_MODEL_DIR "${SHERPA_ONNX_KWS_MODEL_DIR_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" SHERPA_ONNX_KWS_ENCODER "${SHERPA_ONNX_KWS_ENCODER_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" SHERPA_ONNX_KWS_DECODER "${SHERPA_ONNX_KWS_DECODER_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" SHERPA_ONNX_KWS_JOINER "${SHERPA_ONNX_KWS_JOINER_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" SHERPA_ONNX_KWS_TOKENS "${SHERPA_ONNX_KWS_TOKENS_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" SHERPA_ONNX_KWS_KEYWORDS_FILE "${SHERPA_ONNX_KWS_KEYWORDS_FILE_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" ROS_DOMAIN_ID "${ROS_DOMAIN_ID_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" ROS_LOCALHOST_ONLY "${ROS_LOCALHOST_ONLY_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" NO_PROXY "${NO_PROXY_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" no_proxy "${NO_PROXY_VALUE}"
  tmux set-environment -t "${SESSION_NAME}" CYCLONEDDS_ARX_CONFIG "${CYCLONEDDS_ARX_CONFIG}"
  tmux set-environment -t "${SESSION_NAME}" CYCLONEDDS_HOME "${CYCLONEDDS_HOME_VALUE}"
}

start_arx_ros2_window() {
  tmux rename-window -t "${SESSION_NAME}:0" arx_ros2
  send_line arx_ros2 "echo '[arx_ros2] starting ${ARX_ROS2_SCRIPT}'"
  send_line arx_ros2 "bash '${ARX_ROS2_SCRIPT}'"
}

start_arx_bridge_window() {
  tmux new-window -t "${SESSION_NAME}" -n arx_bridge
  send_line arx_bridge "cd '${MAGIC_DIR}' || exit 1"
  send_line arx_bridge "unset ROS_DISTRO"
  send_line arx_bridge "unset LD_PRELOAD"
  send_line arx_bridge "unset PYTHONPATH"
  send_line arx_bridge "source /opt/ros/foxy/setup.bash"
  send_line arx_bridge "source /home/unitree/ARX_X5/ROS2/X5_ws/install/local_setup.bash"
  send_line arx_bridge "export ROS_DOMAIN_ID=\"\$ROS_DOMAIN_ID\""
  send_line arx_bridge "export ROS_LOCALHOST_ONLY=\"\$ROS_LOCALHOST_ONLY\""
  send_line arx_bridge "unset CYCLONEDDS_URI"
  send_line arx_bridge "export CYCLONEDDS_URI=\"file://\$CYCLONEDDS_ARX_CONFIG\""
  send_line arx_bridge "echo '[arx_bridge] CYCLONEDDS_URI='\"\$CYCLONEDDS_URI\""
  send_line arx_bridge "python3.8 system_hw_test/arx_x5_motion_zenoh_bridge.py --standalone-discovery"
}

start_koala_fetch_window() {
  tmux new-window -t "${SESSION_NAME}" -n koala_fetch
  send_line koala_fetch "cd '${MAGIC_DIR}' || exit 1"
  send_line koala_fetch "source /opt/ros/foxy/setup.bash"
  send_line koala_fetch "source /home/unitree/cyclonedds_ws/install/setup.bash"
  send_line koala_fetch "export CYCLONEDDS_HOME=\"\$CYCLONEDDS_HOME\""
  send_line koala_fetch "source /home/unitree/OM1-ros2-sdk/install/setup.bash"
  send_line koala_fetch "export UNITREE_ETHERNET=\"\$UNITREE_ETHERNET\""
  send_line koala_fetch "export DASHSCOPE_API_KEY=\"\$DASHSCOPE_API_KEY\""
  send_line koala_fetch "export ASR_MICROPHONE_NAME=\"\$ASR_MICROPHONE_NAME\""
  send_line koala_fetch "export ASR_ALSA_CARD=\"\$ASR_ALSA_CARD\""
  send_line koala_fetch "export SHERPA_ONNX_KWS_MODEL_DIR=\"\$SHERPA_ONNX_KWS_MODEL_DIR\""
  send_line koala_fetch "export SHERPA_ONNX_KWS_ENCODER=\"\$SHERPA_ONNX_KWS_ENCODER\""
  send_line koala_fetch "export SHERPA_ONNX_KWS_DECODER=\"\$SHERPA_ONNX_KWS_DECODER\""
  send_line koala_fetch "export SHERPA_ONNX_KWS_JOINER=\"\$SHERPA_ONNX_KWS_JOINER\""
  send_line koala_fetch "export SHERPA_ONNX_KWS_TOKENS=\"\$SHERPA_ONNX_KWS_TOKENS\""
  send_line koala_fetch "export SHERPA_ONNX_KWS_KEYWORDS_FILE=\"\$SHERPA_ONNX_KWS_KEYWORDS_FILE\""
  send_line koala_fetch "amixer -c UACDemoV10 set PCM 100% unmute || echo '[koala_fetch] warning: amixer failed'"
  send_line koala_fetch "unset ROS_DISTRO"
  send_line koala_fetch "unset LD_PRELOAD"
  send_line koala_fetch "source /opt/ros/foxy/setup.bash"
  send_line koala_fetch "source /home/unitree/ARX_X5/ROS2/X5_ws/install/setup.bash"
  send_line koala_fetch "export ROS_DOMAIN_ID=\"\$ROS_DOMAIN_ID\""
  send_line koala_fetch "export ROS_LOCALHOST_ONLY=\"\$ROS_LOCALHOST_ONLY\""
  send_line koala_fetch "unset http_proxy HTTP_PROXY https_proxy HTTPS_PROXY ALL_PROXY all_proxy"
  send_line koala_fetch "export NO_PROXY=\"\$NO_PROXY\""
  send_line koala_fetch "export no_proxy=\"\$no_proxy\""
  send_line koala_fetch "export DASHSCOPE_CHAT_MODEL=\"\$DASHSCOPE_CHAT_MODEL\""
  send_line koala_fetch "echo '[koala_fetch] starting MAGIC ${KOALA_FETCH_CONFIG_VALUE}'"
  send_line koala_fetch "uv run --extra dds src/run.py '${KOALA_FETCH_CONFIG_VALUE}'"
}

start_stack() {
  load_env_file
  resolve_env_values
  ensure_prerequisites

  if tmux_has_session; then
    echo "tmux session '${SESSION_NAME}' already exists."
    echo "Use: $0 attach"
    echo "Or:  $0 restart"
    exit 0
  fi

  ensure_navigation_service

  create_cyclonedds_config

  tmux new-session -d -s "${SESSION_NAME}" -n bootstrap
  set_tmux_environment
  start_arx_ros2_window
  start_arx_bridge_window
  start_koala_fetch_window
  tmux select-window -t "${SESSION_NAME}:koala_fetch"

  echo "Started tmux session '${SESSION_NAME}'."
  echo "Attach: tmux attach -t ${SESSION_NAME}"
  echo "Windows: arx_ros2, arx_bridge, koala_fetch"
}

stop_stack() {
  if tmux_has_session; then
    tmux kill-session -t "${SESSION_NAME}"
    echo "Stopped tmux session '${SESSION_NAME}'."
  else
    echo "tmux session '${SESSION_NAME}' is not running."
  fi
}

status_stack() {
  if tmux_has_session; then
    tmux list-windows -t "${SESSION_NAME}"
  else
    echo "tmux session '${SESSION_NAME}' is not running."
    exit 1
  fi
}

attach_stack() {
  if ! tmux_has_session; then
    echo "tmux session '${SESSION_NAME}' is not running." >&2
    exit 1
  fi
  tmux attach -t "${SESSION_NAME}"
}

case "${1:-start}" in
  start)
    start_stack
    ;;
  stop)
    stop_stack
    ;;
  restart)
    stop_stack
    sleep 1
    start_stack
    ;;
  status)
    status_stack
    ;;
  attach)
    attach_stack
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
