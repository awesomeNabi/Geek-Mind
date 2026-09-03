#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Dedicated FAST-LIO entrypoint for the original Unitree mid360_driver. Keep
# this legacy path available for the original Foxy deployment configuration.
export CONTAINER="${CONTAINER:-magic_mini_mid360_nav}"
export CONTAINER_FASTLIO_RUNTIME_DIR="${CONTAINER_FASTLIO_RUNTIME_DIR:-/tmp/unitree_native_slam/fast-lio-runtime}"

exec bash "${SERVICE_DIR}/scripts/fast_lio_mid360_mapping.sh" \
  --driver-mode unitree \
  --config-file unitree_go2_fastlio_autonomy.yaml \
  --output-dir "${MAPS_DIR:-/home/unitree/maps}" \
  --name autonomy_mid360_map \
  --keep-driver \
  "$@"
