#!/usr/bin/env bash
# Shared Mid360 runtime helpers. Source from other scripts; do not execute directly.
set -euo pipefail

_MID360_RUNTIME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_MID360_SERVICE_DIR="$(cd "${_MID360_RUNTIME_DIR}/.." && pwd)"
_MAGIC_DIR="${MAGIC_DIR:-$(cd "${_MID360_SERVICE_DIR}/../../.." && pwd)}"

if [[ -f "${_MAGIC_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${_MAGIC_DIR}/.env"
  set +a
fi

export MAGIC_DIR="${MAGIC_DIR:-${_MAGIC_DIR}}"
export MID360_RUNTIME="${MID360_RUNTIME:-docker}"
export MID360_WORKSPACE_DIR="${MID360_WORKSPACE_DIR:-}"
export MID360_MAPS_DIR="${MID360_MAPS_DIR:-${MAGIC_DIR}/service/unitree_native_slam}"
export DOCKER_CMD="${DOCKER_CMD:-docker}"

mid360_is_host() {
  [[ "${MID360_RUNTIME}" == "host" ]]
}

mid360_default_workspace_dir() {
  if mid360_is_host; then
    printf '%s\n' "${MID360_WORKSPACE_DIR:-${MAGIC_DIR}/service/unitree_native_slam/autonomy_mid360}"
  else
    # MID360_WORKSPACE_DIR is a host path. The Docker image always installs the
    # ROS workspace at this fixed container path.
    printf '%s\n' "/opt/unitree_native_slam"
  fi
}

mid360_install_setup() {
  printf '%s/install/setup.bash\n' "$(mid360_default_workspace_dir)"
}

mid360_service_config_dir() {
  if mid360_is_host; then
    printf '%s/config\n' "$(mid360_default_workspace_dir)"
  else
    printf '%s\n' "/workspace/unitree_native_slam/config"
  fi
}

mid360_prior_graph_file() {
  if mid360_is_host; then
    printf '%s/prior_graphs/my_prior_graph_final.vgh\n' "$(mid360_default_workspace_dir)"
  else
    printf '%s\n' "/workspace/unitree_native_slam/prior_graphs/my_prior_graph_final.vgh"
  fi
}

mid360_emit_ros_env() {
  local workspace_dir setup
  workspace_dir="$(mid360_default_workspace_dir)"
  setup="${workspace_dir}/install/setup.bash"
  cat <<EOS
set +u
source /opt/ros/humble/setup.bash
if [[ -f '${setup}' ]]; then
  source '${setup}'
fi
set -u
export RMW_IMPLEMENTATION="\${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"
EOS
}

mid360_require_runtime() {
  if mid360_is_host; then
    local setup
    setup="$(mid360_install_setup)"
    [[ -f "${setup}" ]] \
      || {
        echo "Mid360 host workspace is missing: ${setup}" >&2
        echo "Build it first: MID360_RUNTIME=host BUILD_JOBS=2 scripts/setup_magic_mini_humble.sh --navigation" >&2
        return 1
      }
    [[ -f /opt/ros/humble/setup.bash ]] \
      || {
        echo "ROS 2 Humble is missing at /opt/ros/humble/setup.bash" >&2
        return 1
      }
    return 0
  fi

  local container="${CONTAINER_NAME:-${MID360_CONTAINER:-magic_mini_mid360_nav}}"
  if ! ${DOCKER_CMD} inspect -f '{{.State.Running}}' "${container}" 2>/dev/null | grep -qx true; then
    echo "Container is not running: ${container}" >&2
    echo "Start it first: bash ${_MID360_RUNTIME_DIR}/run_container.sh" >&2
    return 1
  fi
}

mid360_exec() {
  local container="$1"
  shift

  if ! mid360_is_host; then
    # shellcheck disable=SC2086
    ${DOCKER_CMD} exec -i "${container}" "$@"
    return
  fi

  case "${1:-}" in
    bash)
      shift
      case "${1:-}" in
        -lc)
          shift
          bash -lc "$(mid360_emit_ros_env)
$1"
          ;;
        -s)
          shift
          local user_script
          user_script="$(cat)"
          {
            mid360_emit_ros_env
            printf '%s\n' "${user_script}"
          } | bash -s -- "$@"
          ;;
        *)
          echo "Unsupported host runtime command: bash $*" >&2
          return 2
          ;;
      esac
      ;;
    test)
      "$@"
      ;;
    *)
      "$@"
      ;;
  esac
}

mid360_ros_launch() {
  local launch_cmd="$1"
  if mid360_is_host; then
    bash -lc "$(mid360_emit_ros_env)
${launch_cmd}"
  else
    local container="${CONTAINER_NAME:-${MID360_CONTAINER:-magic_mini_mid360_nav}}"
    mid360_exec "${container}" bash -lc "${launch_cmd}"
  fi
}
