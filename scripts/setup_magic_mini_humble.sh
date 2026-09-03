#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAGIC_DIR="${MAGIC_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
LOCAL_DIR="${MAGIC_DIR}/.local"
REALSENSE_VERSION="${REALSENSE_VERSION:-2.57.7}"
REALSENSE_COMMIT="${REALSENSE_COMMIT:-9a0dd70db1a2c180b69c6c257cd2ee6120505499}"
REALSENSE_SOURCE_DIR="${REALSENSE_SOURCE_DIR:-${LOCAL_DIR}/src/librealsense}"
REALSENSE_BUILD_DIR="${REALSENSE_BUILD_DIR:-${LOCAL_DIR}/build/librealsense-${REALSENSE_VERSION}}"
REALSENSE_PREFIX="${REALSENSE_PREFIX:-${LOCAL_DIR}/librealsense-${REALSENSE_VERSION}}"
BUILD_JOBS="${BUILD_JOBS:-$(nproc)}"

RUN_SYSTEM=false
RUN_PYTHON=false
RUN_REALSENSE=false
RUN_NAVIGATION=false
RUN_REALSENSE_UDEV_ONLY=false
CHECK_ONLY=false
INSTALL_REALSENSE_UDEV=true

usage() {
  cat <<EOF
Usage: $0 [--all] [--system] [--python] [--realsense] [--realsense-udev] [--navigation] [--skip-udev] [--check]

Stages are idempotent and may be rerun independently:
  --system       Install Ubuntu/Humble build and runtime packages (uses sudo)
  --python       Create/sync the uv Python 3.12 environment
  --realsense    Build pinned librealsense ${REALSENSE_VERSION} for the uv Python
  --realsense-udev
                 Install only the RealSense udev rules after a user-space build
  --navigation   Build the Humble Mid360 navigation stack (Docker image or host workspace)
  --skip-udev    Build RealSense without installing system udev rules
  --check        Only report prerequisites; do not install or build
  --all          Run system, python, RealSense, and navigation stages (default)

Environment overrides:
  MAGIC_DIR, BUILD_JOBS, REALSENSE_SOURCE_DIR, REALSENSE_BUILD_DIR,
  REALSENSE_PREFIX, REALSENSE_COMMIT, BASE_IMAGE, IMAGE_NAME, MID360_RUNTIME
EOF
}

if [[ $# -eq 0 ]]; then
  RUN_SYSTEM=true
  RUN_PYTHON=true
  RUN_REALSENSE=true
  RUN_NAVIGATION=true
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      RUN_SYSTEM=true
      RUN_PYTHON=true
      RUN_REALSENSE=true
      RUN_NAVIGATION=true
      ;;
    --system) RUN_SYSTEM=true ;;
    --python) RUN_PYTHON=true ;;
    --realsense) RUN_REALSENSE=true ;;
    --realsense-udev) RUN_REALSENSE_UDEV_ONLY=true ;;
    --navigation) RUN_NAVIGATION=true ;;
    --skip-udev) INSTALL_REALSENSE_UDEV=false ;;
    --check) CHECK_ONLY=true ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

log() {
  printf '[setup-humble] %s\n' "$*"
}

fail() {
  printf '[setup-humble] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

load_env() {
  if [[ -f "${MAGIC_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${MAGIC_DIR}/.env"
    set +a
  fi
}

check_host() {
  [[ -f /etc/os-release ]] || fail "/etc/os-release is missing"
  # shellcheck disable=SC1091
  source /etc/os-release
  [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "22.04" ]] \
    || fail "expected Ubuntu 22.04, found ${PRETTY_NAME:-unknown}"
  [[ "$(uname -m)" == "aarch64" ]] || fail "expected aarch64, found $(uname -m)"
  [[ -f /opt/ros/humble/setup.bash ]] || fail "ROS 2 Humble is missing at /opt/ros/humble"
  require_command uv
  log "host: ${PRETTY_NAME}, $(uname -m), ROS 2 Humble present"
}

install_system_packages() {
  log "installing Ubuntu and ROS 2 dependencies; sudo may request your password"
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends \
    alsa-utils \
    build-essential \
    cmake \
    curl \
    docker.io \
    ffmpeg \
    git \
    libasound2-dev \
    jq \
    libgl1-mesa-dev \
    libglfw3-dev \
    libglu1-mesa-dev \
    libgtk-3-dev \
    libssl-dev \
    libudev-dev \
    libusb-1.0-0-dev \
    pkg-config \
    portaudio19-dev \
    pulseaudio-utils \
    python3-colcon-common-extensions \
    python3-dev \
    python3-numpy \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-pcl-ros \
    ros-humble-sensor-msgs-py \
    tmux \
    v4l-utils
}

sync_python() {
  log "syncing uv environment with dds and wake-word extras"
  cd "${MAGIC_DIR}"
  CYCLONEDDS_HOME="${CYCLONEDDS_HOME:-/home/nvidia/cyclonedds/install}" \
    uv sync --locked --all-groups --extra dds --extra wake-word
  local python_version
  python_version="$(uv run --no-sync python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  [[ "${python_version}" == "3.12" ]] || fail "expected uv Python 3.12, found ${python_version}"
}

prepare_realsense_source() {
  require_command git
  mkdir -p "$(dirname "${REALSENSE_SOURCE_DIR}")" "$(dirname "${REALSENSE_BUILD_DIR}")"
  if [[ ! -d "${REALSENSE_SOURCE_DIR}/.git" ]]; then
    log "initializing librealsense source repository"
    mkdir -p "${REALSENSE_SOURCE_DIR}"
    git -C "${REALSENSE_SOURCE_DIR}" init
    git -C "${REALSENSE_SOURCE_DIR}" remote add origin https://github.com/IntelRealSense/librealsense.git
  fi

  if ! git -C "${REALSENSE_SOURCE_DIR}" diff --quiet \
    || ! git -C "${REALSENSE_SOURCE_DIR}" diff --cached --quiet; then
    fail "librealsense source has local changes: ${REALSENSE_SOURCE_DIR}"
  fi

  local actual_commit
  actual_commit="$(git -C "${REALSENSE_SOURCE_DIR}" rev-parse HEAD 2>/dev/null || true)"
  if [[ "${actual_commit}" != "${REALSENSE_COMMIT}" ]]; then
    log "fetching pinned librealsense commit without repository history"
    local attempt
    for attempt in 1 2 3 4 5; do
      if git -c http.version=HTTP/1.1 -C "${REALSENSE_SOURCE_DIR}" \
        fetch --depth 1 origin "${REALSENSE_COMMIT}"; then
        break
      fi
      if [[ "${attempt}" -eq 5 ]]; then
        fail "could not fetch librealsense commit after ${attempt} attempts"
      fi
      log "librealsense fetch attempt ${attempt} failed; retrying in $((attempt * 5)) seconds"
      sleep $((attempt * 5))
    done
    git -C "${REALSENSE_SOURCE_DIR}" checkout --detach "${REALSENSE_COMMIT}"
    actual_commit="$(git -C "${REALSENSE_SOURCE_DIR}" rev-parse HEAD)"
  else
    log "librealsense source is already at the pinned commit"
  fi
  [[ "${actual_commit}" == "${REALSENSE_COMMIT}" ]] \
    || fail "librealsense commit mismatch: ${actual_commit}"
}

build_realsense() {
  require_command cmake
  [[ -x "${MAGIC_DIR}/.venv/bin/python" ]] \
    || fail "uv environment is missing; run $0 --python first"
  prepare_realsense_source

  local python_version python_install_dir
  python_version="$("${MAGIC_DIR}/.venv/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  python_install_dir="${REALSENSE_PREFIX}/lib/python${python_version}/site-packages/pyrealsense2"

  log "configuring librealsense ${REALSENSE_VERSION} at ${REALSENSE_COMMIT}"
  cmake -S "${REALSENSE_SOURCE_DIR}" -B "${REALSENSE_BUILD_DIR}" \
    -DBUILD_EXAMPLES=OFF \
    -DBUILD_GRAPHICAL_EXAMPLES=OFF \
    -DBUILD_PYTHON_BINDINGS=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DBUILD_TOOLS=OFF \
    -DBUILD_UNIT_TESTS=OFF \
    -DBUILD_WITH_CUDA=OFF \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="${REALSENSE_PREFIX}" \
    -DFORCE_RSUSB_BACKEND=ON \
    -DPYTHON_EXECUTABLE="${MAGIC_DIR}/.venv/bin/python" \
    -DPython3_EXECUTABLE="${MAGIC_DIR}/.venv/bin/python" \
    -DPYTHON_INSTALL_DIR="${python_install_dir}"
  cmake --build "${REALSENSE_BUILD_DIR}" --parallel "${BUILD_JOBS}"
  cmake --install "${REALSENSE_BUILD_DIR}"

  if [[ "${INSTALL_REALSENSE_UDEV}" == "true" ]]; then
    install_realsense_udev_rules
  else
    log "skipping RealSense udev rules; run --realsense-udev when sudo is available"
  fi

  if [[ "${INSTALL_REALSENSE_UDEV}" == "true" ]]; then
    PYTHONPATH="${REALSENSE_PREFIX}/lib/python${python_version}/site-packages${PYTHONPATH:+:${PYTHONPATH}}" \
      "${MAGIC_DIR}/.venv/bin/python" -c \
      'import pyrealsense2 as rs; devices=list(rs.context().query_devices()); print("pyrealsense2", len(devices), "device(s)"); assert devices, "no RealSense device detected"'
  else
    PYTHONPATH="${REALSENSE_PREFIX}/lib/python${python_version}/site-packages${PYTHONPATH:+:${PYTHONPATH}}" \
      "${MAGIC_DIR}/.venv/bin/python" -c \
      'import pyrealsense2; print("pyrealsense2 Python binding imported; device access deferred until udev rules are installed")'
  fi
}

install_realsense_udev_rules() {
  log "installing RealSense udev rules; sudo may request your password"
  local rule
  for rule in 99-realsense-libusb.rules 99-realsense-d4xx-mipi-dfu.rules; do
    [[ -f "${REALSENSE_SOURCE_DIR}/config/${rule}" ]] \
      || fail "RealSense rule is missing: ${REALSENSE_SOURCE_DIR}/config/${rule}; run --realsense first"
    sudo install -m 0644 "${REALSENSE_SOURCE_DIR}/config/${rule}" "/etc/udev/rules.d/${rule}"
  done
  sudo udevadm control --reload-rules
  sudo udevadm trigger
  log "udev rules installed; unplug and reconnect the camera before capture acceptance"
}

build_navigation() {
  if [[ "${MID360_RUNTIME:-docker}" == "host" ]]; then
    log "building the ROS 2 Humble Mid360 navigation workspace on host"
    BUILD_JOBS="${BUILD_JOBS}" \
      bash "${MAGIC_DIR}/service/unitree_native_slam/autonomy_mid360/scripts/build_image.sh"
    return
  fi

  require_command docker
  if ! docker info >/dev/null 2>&1; then
    fail "Docker daemon is not accessible. Add ${USER} to the docker group, run this stage with DOCKER_CMD='sudo docker', or set MID360_RUNTIME=host in .env to build on the host ROS 2 Humble."
  fi
  log "building the ROS 2 Humble Mid360 navigation image"
  BUILD_JOBS="${BUILD_JOBS}" \
    IMAGE_NAME="${MID360_IMAGE:-magic-mini-mid360-nav:humble}" \
    bash "${MAGIC_DIR}/service/unitree_native_slam/autonomy_mid360/scripts/build_image.sh"
}

load_env
check_host

if [[ "${CHECK_ONLY}" == "true" ]]; then
  log "check complete; no changes made"
  exit 0
fi

[[ "${RUN_SYSTEM}" == "false" ]] || install_system_packages
[[ "${RUN_PYTHON}" == "false" ]] || sync_python
[[ "${RUN_REALSENSE}" == "false" ]] || build_realsense
[[ "${RUN_REALSENSE_UDEV_ONLY}" == "false" ]] || install_realsense_udev_rules
[[ "${RUN_NAVIGATION}" == "false" ]] || build_navigation

log "requested setup stages completed"
