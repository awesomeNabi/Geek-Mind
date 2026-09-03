#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DOCKER_CMD="${DOCKER_CMD:-docker}"
IMAGE_NAME="${IMAGE_NAME:-${MID360_IMAGE:-magic-mini-mid360-nav:humble}}"
CONTAINER_NAME="${CONTAINER_NAME:-${MID360_CONTAINER:-magic_mini_mid360_nav}}"
MAPS_DIR="${MAPS_DIR:-${MID360_MAPS_DIR:-$(cd "${SERVICE_DIR}/.." && pwd)}}"
NETWORK_MODE="${NETWORK_MODE:-host}"
CYCLONEDDS_CONFIG_FILE="${CYCLONEDDS_CONFIG_FILE:-}"
CONTAINER_CYCLONEDDS_FILE="/etc/cyclonedds/magic-mini.xml"
RECREATE_CONTAINER="${RECREATE_CONTAINER:-false}"

docker_cmd() {
  # shellcheck disable=SC2086
  ${DOCKER_CMD} "$@"
}

fail() {
  echo "ERROR: $*" >&2
  exit 2
}

if ! docker_cmd image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  echo "Docker image is missing: ${IMAGE_NAME}" >&2
  echo "Build it first: bash ${SERVICE_DIR}/scripts/build_image.sh" >&2
  exit 2
fi

[[ -d "${MAPS_DIR}" ]] || fail "map directory is missing: ${MAPS_DIR}"
if [[ -n "${CYCLONEDDS_CONFIG_FILE}" ]]; then
  [[ -f "${CYCLONEDDS_CONFIG_FILE}" ]] || fail "CycloneDDS config is missing: ${CYCLONEDDS_CONFIG_FILE}"
fi

container_matches() {
  local configured_image container_image_id expected_image_id mounts env_lines
  configured_image="$(docker_cmd inspect -f '{{.Config.Image}}' "${CONTAINER_NAME}")"
  [[ "${configured_image}" == "${IMAGE_NAME}" ]] || return 1
  container_image_id="$(docker_cmd inspect -f '{{.Image}}' "${CONTAINER_NAME}")"
  expected_image_id="$(docker_cmd image inspect -f '{{.Id}}' "${IMAGE_NAME}")"
  [[ "${container_image_id}" == "${expected_image_id}" ]] || return 1

  mounts="$(docker_cmd inspect -f '{{range .Mounts}}{{printf "%s|%s\n" .Source .Destination}}{{end}}' "${CONTAINER_NAME}")"
  grep -Fqx "${MAPS_DIR}|/workspace/maps" <<<"${mounts}" || return 1
  grep -Fqx "${SERVICE_DIR}|/workspace/unitree_native_slam" <<<"${mounts}" || return 1

  env_lines="$(docker_cmd inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${CONTAINER_NAME}")"
  grep -Fqx "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}" <<<"${env_lines}" || return 1
  grep -Fqx "ROS_DOMAIN_ID=${MID360_ROS_DOMAIN_ID:-0}" <<<"${env_lines}" || return 1
  grep -Fqx "ROS_LOCALHOST_ONLY=${ROS_LOCALHOST_ONLY:-0}" <<<"${env_lines}" || return 1

  if [[ -n "${CYCLONEDDS_CONFIG_FILE}" ]]; then
    grep -Fqx "${CYCLONEDDS_CONFIG_FILE}|${CONTAINER_CYCLONEDDS_FILE}" <<<"${mounts}" || return 1
    grep -Fqx "CYCLONEDDS_URI=file://${CONTAINER_CYCLONEDDS_FILE}" <<<"${env_lines}" || return 1
  fi
}

if docker_cmd container inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
  if ! container_matches; then
    if [[ "${RECREATE_CONTAINER}" != "true" ]]; then
      fail "existing container has stale image, ROS environment, map, or DDS mounts. Re-run with RECREATE_CONTAINER=true after confirming no navigation process is active"
    fi
    docker_cmd rm -f "${CONTAINER_NAME}" >/dev/null
    echo "Removed stale container: ${CONTAINER_NAME}"
  else
    if [[ "$(docker_cmd inspect -f '{{.State.Running}}' "${CONTAINER_NAME}")" != "true" ]]; then
      docker_cmd start "${CONTAINER_NAME}" >/dev/null
      echo "Started container: ${CONTAINER_NAME}"
    else
      echo "Container already running: ${CONTAINER_NAME}"
    fi
    exit 0
  fi
fi

run_args=(
  run -d
  --name "${CONTAINER_NAME}"
  --network "${NETWORK_MODE}"
  --label com.magic-mini.service=unitree-native-slam-mid360
  -e "RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"
  -e "ROS_DOMAIN_ID=${MID360_ROS_DOMAIN_ID:-0}"
  -e "ROS_LOCALHOST_ONLY=${ROS_LOCALHOST_ONLY:-0}"
  -v "${SERVICE_DIR}:/workspace/unitree_native_slam:ro"
  -v "${MAPS_DIR}:/workspace/maps:ro"
)

if [[ -n "${CYCLONEDDS_CONFIG_FILE}" ]]; then
  run_args+=(
    -e "CYCLONEDDS_URI=file://${CONTAINER_CYCLONEDDS_FILE}"
    -v "${CYCLONEDDS_CONFIG_FILE}:${CONTAINER_CYCLONEDDS_FILE}:ro"
  )
fi

docker_cmd "${run_args[@]}" "${IMAGE_NAME}" >/dev/null
echo "Created container: ${CONTAINER_NAME}"
