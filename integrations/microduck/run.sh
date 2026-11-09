#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(dirname "$PROJECT_ROOT")"
if [[ "$(basename "$WORKSPACE_ROOT")" == integrations ]]; then
  WORKSPACE_ROOT="$(cd -- "$PROJECT_ROOT/../../.." && pwd)"
fi
export MAGIC_ROOT="${MAGIC_ROOT:-$WORKSPACE_ROOT/MAGIC}"
export MICRODUCK_ROOT="${MICRODUCK_ROOT:-$WORKSPACE_ROOT/microduck_ros2}"
export MAGIC_DUCK_STATE="${MAGIC_DUCK_STATE:-$PROJECT_ROOT/.runtime}"
export PYTHONPATH="$PROJECT_ROOT/src:$MAGIC_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-84}"
mkdir -p "$MAGIC_DUCK_STATE"
cd "$PROJECT_ROOT"
TASK="${1:-help}"
if (( $# )); then shift; fi
if [[ "$TASK" == help || "$TASK" == --help || "$TASK" == -h ]]; then
  echo 'Usage: bash run.sh {chat|setup|sim-env|up|sim|nav|observer|bridge|state|action|stop|reset|image|demo|plan|ask|mcp|test|smoke}'
  exit 0
fi
if [[ "$TASK" == sim-env ]]; then
  exec bash "$PROJECT_ROOT/scripts/microduck-server.sh" "$@"
fi
if [[ ! -x "$MAGIC_ROOT/.venv/bin/python" ]]; then
  echo "Missing MAGIC interpreter: $MAGIC_ROOT/.venv/bin/python. Prepare MAGIC's environment or export MAGIC_ROOT; see README.md." >&2
  exit 1
fi
if [[ "$TASK" == sim || "$TASK" == nav ]]; then
  WALKING_POLICY="${MICRODUCK_WALKING_POLICY:-$("$MAGIC_ROOT/.venv/bin/python" -m magic_microduck.assets)}"
fi
case "$TASK" in
  setup) exec "$MAGIC_ROOT/.venv/bin/python" -m magic_microduck.assets ;;
  up) exec "$MAGIC_ROOT/.venv/bin/python" -m magic_microduck.stack "$@" ;;
  chat) exec "$MAGIC_ROOT/.venv/bin/python" -m magic_microduck.console "$@" ;;
  observer) exec bash "$PROJECT_ROOT/scripts/microduck-server.sh" exec env PYTHONPATH="$MICRODUCK_ROOT/microduck_sim:$PYTHONPATH" python -m magic_microduck.observer "$@" ;;
  sim) exec bash "$PROJECT_ROOT/scripts/microduck-server.sh" sim "walking_policy:=$WALKING_POLICY" "$@" ;;
  nav)
    "$MAGIC_ROOT/.venv/bin/python" -m magic_microduck.nav_config
    exec bash "$PROJECT_ROOT/scripts/microduck-server.sh" nav "walking_policy:=$WALKING_POLICY" "nav_params:=$MAGIC_DUCK_STATE/nav2.generated.yaml" "$@"
    ;;
  bridge) exec bash "$PROJECT_ROOT/scripts/microduck-server.sh" exec env PYTHONPATH="$PYTHONPATH" python -m magic_microduck.bridge "$@" ;;
  mcp) exec "$MAGIC_ROOT/.venv/bin/python" -m magic_microduck.mcp_server "$@" ;;
  test) exec "$MAGIC_ROOT/.venv/bin/python" -m pytest -q "$PROJECT_ROOT/tests" "$@" ;;
  smoke) exec "$MAGIC_ROOT/.venv/bin/python" "$PROJECT_ROOT/scripts/smoke.py" "$@" ;;
  *) exec "$MAGIC_ROOT/.venv/bin/python" -m magic_microduck.cli "$TASK" "$@" ;;
esac
