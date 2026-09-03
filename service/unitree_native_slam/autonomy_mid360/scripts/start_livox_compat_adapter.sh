#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/mid360_runtime.sh"

CONTAINER_NAME="${CONTAINER_NAME:-${MID360_CONTAINER:-magic_mini_mid360_nav}}"
WORKSPACE_DIR="${WORKSPACE_DIR:-$(mid360_default_workspace_dir)}"
INPUT_TOPIC="${LIVOX_INPUT_TOPIC:-/livox/lidar}"
OUTPUT_TOPIC="${FASTLIO_INPUT_TOPIC:-/unitree/slam_lidar/points}"

mid360_require_runtime

launch_cmd="set -euo pipefail
set +u
source /opt/ros/humble/setup.bash
source '${WORKSPACE_DIR}/install/setup.bash'
set -u
export RMW_IMPLEMENTATION=\${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}
exec ros2 run mid360_go2_nav_bridge livox_pointcloud_compat_bridge --ros-args \
  -p input_topic:='${INPUT_TOPIC}' \
  -p output_topic:='${OUTPUT_TOPIC}'"

if mid360_is_host; then
  if [[ -t 0 && -t 1 ]]; then
    bash -lc "$(mid360_emit_ros_env)
${launch_cmd}"
  else
    bash -lc "$(mid360_emit_ros_env)
${launch_cmd}"
  fi
else
  exec_args=(exec)
  if [[ -t 0 && -t 1 ]]; then
    exec_args+=(-it)
  fi
  # shellcheck disable=SC2086
  ${DOCKER_CMD} "${exec_args[@]}" "${CONTAINER_NAME}" bash -lc "${launch_cmd}"
fi
