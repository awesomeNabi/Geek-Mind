#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# The compatibility node publishes the original x/y/z/intensity/ring/time
# layout. FAST-LIO consumes Go2's native reliable 200 Hz /livox/imu directly.
export CONTAINER="${CONTAINER:-magic_mini_mid360_nav}"
export CONTAINER_FASTLIO_RUNTIME_DIR="${CONTAINER_FASTLIO_RUNTIME_DIR:-/tmp/unitree_native_slam/fast-lio-runtime}"
export FASTLIO_IMU_TOPIC="${FASTLIO_IMU_TOPIC:-/livox/imu}"

exec bash "${SERVICE_DIR}/scripts/fast_lio_mid360_mapping.sh" \
  --driver-mode external \
  --config-file unitree_go2_fastlio_autonomy.yaml \
  --output-dir "${MAPS_DIR:-$(cd "${SERVICE_DIR}/.." && pwd)}" \
  --name autonomy_mid360_map \
  "$@"
