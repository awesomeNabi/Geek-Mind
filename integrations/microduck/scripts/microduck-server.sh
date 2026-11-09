#!/usr/bin/env bash
# Headless ROS 2 environment, called by run.sh with MICRODUCK_ROOT exported.
# bash run.sh sim-env install              # install the upstream Pixi ci environment
# bash run.sh sim-env fetch                # fetch upstream model and policies
# bash run.sh sim-env build                # build the upstream ROS workspace
# bash run.sh sim-env exec ros2 topic list --no-daemon
set -euo pipefail
PROJECT_ROOT="${MICRODUCK_ROOT:?Run this helper through bash run.sh sim-env, or export MICRODUCK_ROOT}"
cd "$PROJECT_ROOT"
PROJECT_ROOT="$PWD"
export PIXI_CACHE_DIR="$PROJECT_ROOT/.local/cache/pixi"
export UV_CACHE_DIR="$PROJECT_ROOT/.local/cache/uv"
export HF_HOME="$PROJECT_ROOT/.local/cache/huggingface"
export MICRODUCK_RL_PATH="${MICRODUCK_RL_PATH:-$PROJECT_ROOT/.local/assets/microduck_rl}"
export MICRODUCK_POLICIES_PATH="${MICRODUCK_POLICIES_PATH:-$PROJECT_ROOT/.local/assets/microduck-policies}"
export ROS_LOG_DIR="$PROJECT_ROOT/.local/logs/ros"
export ROS_HOME="$PROJECT_ROOT/.local/ros"
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-84}"
export OPENBLAS_NUM_THREADS="${MICRODUCK_CPU_THREADS:-2}"
export OMP_NUM_THREADS="${MICRODUCK_CPU_THREADS:-2}"
export LP_NUM_THREADS="${MICRODUCK_CPU_THREADS:-2}"
mkdir -p "$ROS_LOG_DIR" "$ROS_HOME" "$PROJECT_ROOT/.local/maps"
PIXI="$PROJECT_ROOT/.local/bin/pixi"
if [[ ! -x "$PIXI" ]]; then
    PIXI="$(command -v pixi || true)"
    if [[ -z "$PIXI" ]]; then
        echo "Pixi not found at $PROJECT_ROOT/.local/bin/pixi or on PATH. Install Pixi before preparing the simulator." >&2
        exit 1
    fi
fi
TASK="${1:-sim}"
if (( $# )); then shift; fi
case "$TASK" in
    install) exec "$PIXI" install -e ci "$@" ;;
    sim) exec "$PIXI" run -e ci sim rviz:=false "$@" ;;
    nav) exec "$PIXI" run -e ci nav rviz:=false "map:=$PROJECT_ROOT/.local/maps/apartment.yaml" "$@" ;;
    exec) exec "$PIXI" run -e ci bash -c 'source .ws/install/setup.bash && exec "$@"' -- "$@" ;;
    *) exec "$PIXI" run -e ci "$TASK" "$@" ;;
esac
