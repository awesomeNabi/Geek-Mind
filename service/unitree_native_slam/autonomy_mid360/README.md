# MAGIC_MINI Mid360 navigation service

This directory contains the source and runtime scripts used by the optional
`unitree_go2_koala_fetch_single_mode_autonomy_mid360` configuration. It replaces
the previous runtime dependency on `/home/unitree/go2-fast-lio`.

## Included

- FAST-LIO and Open3D localization ROS 2 packages.
- The autonomy local planner, FAR planner, graph decoder, Unitree messages, and
  the local Mid360 bridge package.
- A pinned prior visibility graph and the guarded goal/boundary scripts.
- A Dockerfile that builds one ROS 2 Humble image for the complete chain.

Generated ROS workspaces, bags, logs, backups, and simulator assets are not
included. The workplace PCD map is intentionally not committed as source data.

## One-time setup

The validated MAGIC_MINI host provides Docker, tmux, a direct MID360S driver
workspace at `/home/nvidia/ws_mid360`, and the map referenced by the MAGIC
configuration. The sensor uses `enx00e04c680d5f` with host address
`192.168.200.1/24`; the lidar is `192.168.200.20`.

From the MAGIC_MINI root:

```bash
bash service/unitree_native_slam/autonomy_mid360/scripts/build_image.sh
bash service/unitree_native_slam/autonomy_mid360/scripts/run_container.sh
```

The build uses Tsinghua TUNA mirrors by default for Ubuntu Ports (including
security), ROS 2, and PyPI. Stage 1 rewrites both classic `.list` and DEB822
`.sources` apt entries and fails if official hosts remain. To temporarily fall
back to the image's original apt and pip sources:

```bash
USE_TUNA_MIRROR=0 \
  bash service/unitree_native_slam/autonomy_mid360/scripts/build_image.sh
```

Mirror URLs, retry counts, and per-request timeouts are configurable through
`UBUNTU_APT_MIRROR`, `ROS2_APT_MIRROR`, `PYPI_INDEX_URL`, `APT_RETRIES`,
`APT_TIMEOUT_SECONDS`, `PIP_RETRIES`, and `PIP_TIMEOUT_SECONDS`.

If Docker Hub is unavailable but the robot already has a compatible Humble
image, it can be used as the build base without changing the committed
Dockerfile default:

```bash
BASE_IMAGE=unitree_humble_dev:latest \
  bash service/unitree_native_slam/autonomy_mid360/scripts/build_image.sh
```

For an offline compile check against that pre-provisioned image, the already
installed ROS packages can be reused with `INSTALL_ROS_DEPS=0`. This override
is for local validation; release builds should keep the default value `1`.

## Build stages and likely stalls

The script and Dockerfile print explicit stage labels:

| Output | Work | Common reason for a long wait |
| --- | --- | --- |
| `preflight 1/2` | Inspect or pull `BASE_IMAGE` | Docker Hub is unreachable or rate-limited. TUNA apt mirrors cannot accelerate registry pulls. |
| `stage 1/6` | Rewrite apt sources | Normally completes immediately; a failure indicates an unexpected base-image source layout. |
| `stage 2/6` | `apt update` and install native/ROS packages | Mirror connectivity, ROS index synchronization, or the relatively large Foxglove package. Requests retry up to `APT_RETRIES` with `APT_TIMEOUT_SECONDS` per request. |
| `stage 3/6` | Install PyYAML and transforms3d | PyPI mirror connectivity. |
| `stage 4/6` | Compile Livox-SDK2 | CPU/RAM pressure; usually much shorter than the ROS workspace build. |
| `stage 5/6` | Compile the bundled ROS workspace | The longest CPU-heavy phase. The live output names each colcon package; FAST-LIO, Open3D localization, local planner, and FAR planner are the likely slow packages. An abrupt `Killed` usually means out-of-memory; lower `BUILD_JOBS` to `1`. |
| `stage 6/6` | Verify the unified install | A failure means the colcon install did not produce `setup.bash`. |

If output stops before `stage 1/6`, inspect Docker registry access. If it stops
inside `stage 2/6`, the last displayed repository/package identifies the
download. If it stops inside `stage 5/6`, the last `Starting >>>` or compiler
line identifies the ROS package being built.

The image defaults to `magic-mini-mid360-nav:humble` and the container defaults
to `magic_mini_mid360_nav`. `MAPS_DIR`, `IMAGE_NAME`, `CONTAINER_NAME`,
`MID360_ROS_DOMAIN_ID`, and `DOCKER_CMD` can be overridden in the environment.
The top-level `scripts/start_magic_mini_humble.sh` launcher also supports
`MID360_DRIVER_AUTOSTART`, `MID360_DRIVER_SCRIPT`, `MID360_DRIVER_SETUP`,
`MID360_DRIVER_INTERFACE`, `MID360_DRIVER_HOST_IP`, and `MID360_LIDAR_IP`. It
requires live `/livox/lidar` and `/livox/imu` messages before starting the
navigation runtime.

Then start the Mid360 MAGIC variant:

```bash
KOALA_FETCH_CONFIG=unitree_go2_koala_fetch_single_mode_autonomy_mid360 \
  scripts/start_magic_mini_stack.sh start
```

## Runtime layout

- Project service mount: `/workspace/unitree_native_slam` (read-only)
- Map mount: `/workspace/maps` (read-only)
- Unified ROS install: `/opt/unitree_native_slam/install/setup.bash`
- Temporary FAST-LIO output: `/tmp/unitree_native_slam/fast-lio-runtime`

The service uses host networking so ROS 2 DDS can discover the Unitree driver
and the rest of the robot graph.

## V-Graph startup readiness

When a prior graph is enabled, startup does not treat a nonzero
`/robot_vgraph.size` as sufficient. The read-only
`scripts/check_vgraph_ready.py` probe parses the prior graph's main connected
component, examines all finalized V-Graph nodes near `/baselink2map`, and waits
until at least one nearby node belongs to a sufficiently large component for
several consecutive graph samples. It never publishes `/goal_point` or a motion
command.

The readiness gate is controlled by these lifecycle-hook settings:

- `vgraph_readiness_check_enabled`
- `vgraph_readiness_consecutive_samples`
- `vgraph_readiness_sample_interval_seconds`
- `vgraph_readiness_min_prior_component_ratio`
- `vgraph_readiness_max_robot_node_distance`

For the company graph, the prior main component contains 458 nodes. The current
profile requires 90 percent of that component, a robot-to-node distance of at
most 1 meter, and three consecutive passing samples. Failure keeps startup from
accepting voice navigation goals and reports the observed component size and
selected attachment-node distance.
