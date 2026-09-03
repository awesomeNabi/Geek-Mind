#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/mid360_runtime.sh"

DOCKER_CMD="${DOCKER_CMD:-docker}"
IMAGE_NAME="${IMAGE_NAME:-magic-mini-mid360-nav:humble}"
BUILD_JOBS="${BUILD_JOBS:-2}"
BASE_IMAGE="${BASE_IMAGE:-ros:humble-ros-base}"
INSTALL_APT_DEPS="${INSTALL_APT_DEPS:-1}"
INSTALL_ROS_DEPS="${INSTALL_ROS_DEPS:-1}"
INSTALL_PIP_DEPS="${INSTALL_PIP_DEPS:-1}"
USE_TUNA_MIRROR="${USE_TUNA_MIRROR:-1}"
UBUNTU_APT_MIRROR="${UBUNTU_APT_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports}"
ROS2_APT_MIRROR="${ROS2_APT_MIRROR:-https://mirrors.tuna.tsinghua.edu.cn/ros2/ubuntu}"
PYPI_INDEX_URL="${PYPI_INDEX_URL:-https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple}"
APT_RETRIES="${APT_RETRIES:-5}"
APT_TIMEOUT_SECONDS="${APT_TIMEOUT_SECONDS:-60}"
PIP_RETRIES="${PIP_RETRIES:-5}"
PIP_TIMEOUT_SECONDS="${PIP_TIMEOUT_SECONDS:-60}"

build_host_workspace() {
  local workspace_dir install_dir livox_build livox_src host_python
  workspace_dir="$(mid360_default_workspace_dir)"
  install_dir="${workspace_dir}/install"
  livox_src="${SERVICE_DIR}/third_party/Livox-SDK2"
  livox_build="${SERVICE_DIR}/.build/Livox-SDK2"
  host_python="/usr/bin/python3"

  echo "[host 1/4] Installing native and ROS 2 build dependencies"
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libapr1-dev \
    liblapacke-dev \
    libopencv-dev \
    libopen3d-dev \
    libpcl-dev \
    libusb-1.0-0-dev \
    libyaml-cpp-dev \
    python3-colcon-common-extensions \
    python3-empy \
    python3-numpy \
    python3-pip \
    python3-transforms3d \
    python3-yaml \
    ros-humble-ament-cmake-auto \
    ros-humble-cv-bridge \
    ros-humble-demo-nodes-cpp \
    ros-humble-foxglove-bridge \
    ros-humble-image-transport \
    ros-humble-perception-pcl \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-rosidl-generator-dds-idl \
    ros-humble-rviz2 \
    ros-humble-sensor-msgs-py \
    ros-humble-tf-transformations \
    ros-humble-tf2-eigen \
    ros-humble-tf2-geometry-msgs \
    ros-humble-tf2-ros \
    ros-humble-tf2-sensor-msgs \
    ros-humble-urdf \
    tmux

  echo "[host 2/4] Verifying ROS 2 Python tooling (${host_python})"
  "${host_python}" -c 'import sys; assert sys.version_info[:2] == (3, 10), sys.version'
  "${host_python}" -c 'import em; import yaml; import transforms3d'

  echo "[host 3/4] Building Livox-SDK2"
  cmake -S "${livox_src}" -B "${livox_build}" -DCMAKE_BUILD_TYPE=Release
  cmake --build "${livox_build}" --parallel "${BUILD_JOBS}"
  sudo cmake --install "${livox_build}"
  sudo ldconfig

  echo "[host 4/4] Building bundled ROS 2 workspace with colcon"
  # Keep ROS 2 Humble on system Python 3.10; conda/base env must not win during colcon.
  export PATH="/usr/bin:/bin:/usr/local/bin:/opt/ros/humble/bin:${PATH}"
  export PYTHON_EXECUTABLE="${host_python}"
  # ROS setup scripts read optional variables that may be unset under nounset.
  set +u
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash
  set -u
  export ROS_EDITION=ROS2 DISTRO_ROS=humble
  colcon --log-base "${SERVICE_DIR}/.build/colcon-log" build \
    --event-handlers console_direct+ \
    --base-paths "${SERVICE_DIR}/workspace/src" \
    --build-base "${SERVICE_DIR}/.build/colcon-build" \
    --install-base "${install_dir}" \
    --merge-install \
    --parallel-workers "${BUILD_JOBS}" \
    --cmake-args \
      -DCMAKE_BUILD_TYPE=Release \
      -DROS_EDITION=ROS2 \
      -DDISTRO_ROS=humble \
      -DPython3_EXECUTABLE="${host_python}" \
      -DPYTHON_EXECUTABLE="${host_python}"

  [[ -f "${install_dir}/setup.bash" ]] || {
    echo "Host colcon build did not produce ${install_dir}/setup.bash" >&2
    exit 1
  }
  echo "Built host Mid360 workspace: ${install_dir}/setup.bash"
}

if mid360_is_host; then
  build_host_workspace
  exit 0
fi

echo "[preflight 1/2] Checking base image: ${BASE_IMAGE}"
if ! ${DOCKER_CMD} image inspect "${BASE_IMAGE}" >/dev/null 2>&1; then
  echo "Base image is not cached locally; pulling from its registry."
  echo "TUNA apt/pip mirrors do not accelerate this Docker registry pull."
  ${DOCKER_CMD} pull "${BASE_IMAGE}"
fi

echo "[preflight 2/2] Building image: ${IMAGE_NAME}"
echo "Build mirrors: TUNA=${USE_TUNA_MIRROR}, Ubuntu=${UBUNTU_APT_MIRROR}, ROS2=${ROS2_APT_MIRROR}, PyPI=${PYPI_INDEX_URL}"

${DOCKER_CMD} build \
  --build-arg "BASE_IMAGE=${BASE_IMAGE}" \
  --build-arg "BUILD_JOBS=${BUILD_JOBS}" \
  --build-arg "INSTALL_APT_DEPS=${INSTALL_APT_DEPS}" \
  --build-arg "INSTALL_ROS_DEPS=${INSTALL_ROS_DEPS}" \
  --build-arg "INSTALL_PIP_DEPS=${INSTALL_PIP_DEPS}" \
  --build-arg "USE_TUNA_MIRROR=${USE_TUNA_MIRROR}" \
  --build-arg "UBUNTU_APT_MIRROR=${UBUNTU_APT_MIRROR}" \
  --build-arg "ROS2_APT_MIRROR=${ROS2_APT_MIRROR}" \
  --build-arg "PYPI_INDEX_URL=${PYPI_INDEX_URL}" \
  --build-arg "APT_RETRIES=${APT_RETRIES}" \
  --build-arg "APT_TIMEOUT_SECONDS=${APT_TIMEOUT_SECONDS}" \
  --build-arg "PIP_RETRIES=${PIP_RETRIES}" \
  --build-arg "PIP_TIMEOUT_SECONDS=${PIP_TIMEOUT_SECONDS}" \
  -t "${IMAGE_NAME}" \
  -f "${SERVICE_DIR}/docker/Dockerfile.humble" \
  "${SERVICE_DIR}"

echo "Built image: ${IMAGE_NAME}"
