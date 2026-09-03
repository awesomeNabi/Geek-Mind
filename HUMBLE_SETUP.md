# MAGIC_MINI Ubuntu 22.04 + ROS 2 Humble 部署与验收

本文档针对当前主机 `/home/nvidia/MAGIC_MINI`。目标是先跑通 Go2 + Mid360 + FAST-LIO + 既有地图导航、D435i、语音链路；当前阶段明确不安装、不启动 ARX 机械臂相关组件。

## 1. 适配结论

原项目来自 Ubuntu 20.04 + ROS 2 Foxy，不能直接复用其中的 Python、ROS overlay 或 RealSense wheel。本机方案采用以下边界：

| 项目 | 本机方案 |
| --- | --- |
| 操作系统 / 架构 | Ubuntu 22.04 / aarch64 |
| ROS | ROS 2 Humble；导航放在 Humble Docker 容器中 |
| MAGIC Python | `uv` 管理的 Python 3.12；启动前清除 ROS Python 3.10 路径 |
| Go2 DDS | 主机 `eno1`，CycloneDDS，`ROS_DOMAIN_ID=0` |
| Mid360 | MID360S 直连 `enx00e04c680d5f`；主机 `192.168.200.1`，雷达 `192.168.200.20` |
| FAST-LIO 输入 | 兼容桥只转换点云到 `/unitree/slam_lidar/points`；IMU 直接使用原生可靠 200 Hz `/livox/imu` |
| RealSense | 固定 librealsense 2.57.7、RSUSB、静态构建、Python 3.12 binding |
| 地图 | 优先复用现有 PCD、先验图和边界；验收失败后才重建地图 |
| ARX | 配置、启动流程、提示词和动作列表中均禁用 |
| 实机运动 | 启动时自动站立；当前配置同时启用低速实机导航，必须有人监护并保持急停可用 |

参考原始 FAST-LIO 部署后，本地地图、先验图及核心导航源码与原机版本一致。当前固定文件摘要为：

```text
map sha256:   596e9376ad48bc688133f8864122fabda76305c09e82a1f5e567b7805067057c
prior sha256: 760ac228a30e26e92ecebbf1d1b9e637bd8e74f63aaa8eb6eb35944afa06ed3b
```

## 2. 首次部署前必须处理

### 2.1 Docker 权限

当前主机已安装 Docker CLI，但普通用户若看到 `/var/run/docker.sock: permission denied`，需要执行一次：

```bash
sudo usermod -aG docker "$USER"
```

然后完整注销并重新登录。也可在当前终端临时执行 `newgrp docker`。确认：

```bash
docker info >/dev/null
```

不要把 Docker socket 改成全员可写。

### 2.2 环境文件与密钥

```bash
cd /home/nvidia/MAGIC_MINI
test -f .env || cp .env.example .env
${EDITOR:-nano} .env
```

至少填写一个新建的 `DASHSCOPE_API_KEY`。旧文档中出现过明文密钥，建议将旧密钥作废并轮换；不要提交 `.env`，也不要把它贴进日志。

默认硬件值已经按本机填写：

- Go2 网口：`eno1`
- MID360S 网口：`enx00e04c680d5f`，主机 `192.168.200.1/24`
- MID360S 地址：`192.168.200.20`，驱动工作区 `/home/nvidia/ws_mid360`
- D435i 序列号：`254843066143`
- 地图目录：`/home/nvidia/MAGIC_MINI/service/unitree_native_slam`
- 安全配置：`unitree_go2_koala_nav_vision_no_arm`

### 2.3 MID360S 直连网络

本机的 `/livox/lidar` 和 `/livox/imu` 不是 Go2 自带话题，而是由
`/home/nvidia/ws_mid360/scripts/start_mid360s.sh` 发布。确认独立网卡和雷达可达：

```bash
ip -4 address show dev enx00e04c680d5f
ping -c 3 192.168.200.20
```

网卡必须包含 `192.168.200.1/24`。统一启动脚本默认自动管理该驱动，并在继续启动
FAST-LIO 前分别等待一帧 `/livox/lidar` 和 `/livox/imu`。不要再手动启动第二份
`livox_ros_driver2_node`。

## 3. 分阶段安装

安装脚本可重复执行，失败后只需重跑对应阶段。

### 3.1 系统依赖

```bash
cd /home/nvidia/MAGIC_MINI
scripts/setup_magic_mini_humble.sh --system
```

该阶段需要 `sudo`，会安装编译工具、音频工具、Docker、`pcl_ros`、CycloneDDS RMW 等 Humble 依赖。

### 3.2 Python 3.12 环境

先确保 `uv` 已安装，然后运行：

```bash
scripts/setup_magic_mini_humble.sh --python
```

脚本使用锁文件同步 `dds` 和 `wake-word` extras，并强制使用本机 `/home/nvidia/cyclonedds/install` 编译 CycloneDDS Python binding。

### 3.3 RealSense D435i

完整安装：

```bash
BUILD_JOBS=4 scripts/setup_magic_mini_humble.sh --realsense
```

如果当前无法输入 `sudo` 密码，可先完成用户态构建：

```bash
BUILD_JOBS=4 scripts/setup_magic_mini_humble.sh --realsense --skip-udev
```

之后只安装 udev 规则：

```bash
scripts/setup_magic_mini_humble.sh --realsense-udev
```

安装规则后拔插一次 D435i。

不要安装来自 Foxy/Ubuntu 20.04 或其他 Python 版本的 `pyrealsense2` wheel。本方案固定：

```text
librealsense version: 2.57.7
commit: 9a0dd70db1a2c180b69c6c257cd2ee6120505499
backend: RSUSB
prefix: /home/nvidia/MAGIC_MINI/.local/librealsense-2.57.7
```

### 3.4 FAST-LIO 与导航镜像

Docker 权限正常后运行：

```bash
BUILD_JOBS=2 scripts/setup_magic_mini_humble.sh --navigation
docker image inspect magic-mini-mid360-nav:humble >/dev/null
```

内存紧张或编译进程被杀时改为 `BUILD_JOBS=1`。导航源码、Livox 点云兼容桥、FAST-LIO、重定位及规划器会一起编进镜像。

一次完成所有阶段也可以使用：

```bash
BUILD_JOBS=2 scripts/setup_magic_mini_humble.sh --all
```

## 4. 安全启动

> `start` 会通过 Go2 Sport API 立即执行 `StandUp` 和 `BalanceStand`。启动前必须清空机器人周围区域并确认急停可用。

先做静态检查：

```bash
scripts/setup_magic_mini_humble.sh --check
scripts/start_magic_mini_humble.sh check
```

启动：

```bash
scripts/start_magic_mini_humble.sh start
scripts/start_magic_mini_humble.sh status
```

查看或停止：

```bash
scripts/start_magic_mini_humble.sh attach
scripts/start_magic_mini_humble.sh stop
```

当前配置的运动边界：

1. LLM 没有抓取、递送或机械臂动作。
2. Go2 站立 hook 以最高启动优先级执行；站立失败会中止启动，不进入导航状态。
3. 导航 action 和 `pathFollower` 的实机门控当前均已开启，会向 Go2 sport API 发送运动请求；速度仍限制为 `0.05 m/s`、`10 deg/s`。

启动 hook 的顺序是：Go2 站立并进入平衡姿态、Livox 兼容桥、FAST-LIO、地图重定位、FAR/局部规划器。站立、关键话题或先验图检查任一失败都会中止进入可导航状态。

外层脚本的完整顺序是：清理遗留导航容器和 tmux 会话、启动直连 MID360S 驱动并验证真实数据、启动 Humble 导航容器、最后启动 MAGIC。`stop` 即使在 MAGIC 主会话已经退出时，也会继续清理导航容器和由脚本管理的雷达驱动。

## 5. 详细验收

验收工具会同时生成 JSON 和 Markdown 报告到 `.runtime/verification/`。返回码 `0` 表示全部通过，`1` 表示确定失败，`2` 表示因权限、设备或未启动服务而阻塞。

### 5.1 不依赖机器人的检查

```bash
env -u PYTHONPATH -u AMENT_PREFIX_PATH -u CMAKE_PREFIX_PATH \
  -u COLCON_PREFIX_PATH -u ROS_DISTRO -u ROS_VERSION -u ROS_PYTHON_VERSION \
  CYCLONEDDS_HOME=/home/nvidia/cyclonedds/install \
  uv run --no-sync python tools/verify_humble_environment.py \
  --stage host --stage python
```

这一步核验 OS/架构、Humble、网口、CycloneDDS、无机械臂配置、地图摘要、Docker、Python 3.12 和关键模块。

### 5.2 D435i 连续采集

```bash
uv run --no-sync python tools/verify_humble_environment.py --stage realsense --camera-frames 300
```

通过标准：指定序列号连续取得 300 组对齐 RGB-D 帧，实际帧率不低于 12 FPS，抽样深度有效像素比例不低于 30%。

### 5.3 Mid360、FAST-LIO 与既有地图

将 Go2 放在原建图起点，保持静止、场地清空且急停可用。启动完整栈后运行：

```bash
uv run --no-sync python tools/verify_humble_environment.py \
  --stage dds --stage fastlio --stage localization --duration 60
```

通过标准：

| 检查 | 标准 |
| --- | --- |
| 原始和转换后点云 | 18-22 Hz；字段正确；单帧时间跨度 45-55 ms |
| FAST-LIO 原生 IMU | 180-220 Hz |
| FAST-LIO 静止漂移 | 60 秒位置不超过 0.10 m，航向不超过 2 度 |
| 地图定位置信度 | 中位数至少 0.85，最低至少 0.80 |
| 定位跳变 | 相邻位置不超过 0.25 m，航向不超过 5 度 |

若定位不通过，先检查机器人是否确实位于原建图起点、Mid360 安装方向和时间戳，再考虑重建地图。不要用调低置信度阈值掩盖错误坐标系或错误地图。

### 5.4 仅规划模式（需使用安全配置副本）

当前配置已经启用实机导航，不能直接把以下检查当作“不会运动”的保证。若需要仅规划验收，先复制配置，在副本中同时设置 lifecycle 的 `real_robot=false` 和 action 的 `allow_real_robot_goal=false`，用该副本重启后再确认：

```bash
uv run --no-sync python tools/verify_humble_environment.py --stage no-motion-nav
```

机器人确实放在原建图起点后，再允许发布地图坐标 `(0.5, 0, 0)` 的仅规划目标：

```bash
uv run --no-sync python tools/verify_humble_environment.py \
  --stage no-motion-nav --origin-confirmed
```

工具会验证 FAR 路径、局部路径、`/cmd_vel`，并检查规划速度不超过 `0.05 m/s`、航向角速度不超过 `10 deg/s`。结束时会主动发布到达状态清除目标。只有报告明确确认 `is_real_robot=false` 时，该阶段才不会连接 Go2 sport 命令。

### 5.5 音频、唤醒、ASR 与 TTS

先接入配置中的 USB 麦克风和扬声器：

```bash
arecord -l
aplay -l
uv run --no-sync python tools/verify_humble_environment.py --stage audio
```

设备检查通过后进行人工验收：

1. 录制 10 秒语音，确认不是静音、无持续削顶和明显丢帧。
2. 在 0.5-2 m 距离说 5 次唤醒词，至少成功 4 次。
3. 说一条固定中文指令，检查实时 ASR 最终文本完整且没有重复提交。
4. 触发一条固定 TTS，检查扬声器、超时和播放结束状态。
5. TTS 播放时不应把自己的语音反复识别成新指令。

当前若 `arecord -l` / `aplay -l` 只显示 Jetson 内置声卡，音频全链路只能标记为阻塞，不能视为通过。

### 5.6 汇总检查

所有硬件已连接且服务已经启动时：

```bash
uv run --no-sync python tools/verify_humble_environment.py --all-safe --duration 60 --camera-frames 300
```

保存报告中的失败项、话题频率和漂移数据，不要只保留终端最后一行。

## 6. 最后阶段：有人监护的低速实机导航

只有前述检查全部通过后才进行。此步骤不会由验收工具自动启动。

1. 两人配合，一人观察日志，一人手持急停；清出至少 2 m x 2 m 空地。
2. 启动脚本会自动让 Go2 站立；确认其已进入平衡姿态，并检查电量、网络和定位稳定。
3. 确认导航 lifecycle 的 `real_robot` 和 action 的 `allow_real_robot_goal` 均为 `true`；保持 `max_speed=0.05`、`max_yaw_rate=10.0`、`stand_up_before_navigation=false`。
4. 重启完整栈，先再次确认 `/pathFollower` 参数和定位置信度。
5. 先发 0.5 m 直行目标，再发回到起点的目标；任一方向、速度或坐标异常立即急停。
6. 断开点云、里程计或定位输入各一次，确认 watchdog 锁止、清零速度并重复发送 `StopMove`；只有输入恢复且收到新的目标后才能重新解锁。
7. 测试结束立即恢复安全配置，并检查 Git diff，避免把实机开关误提交为默认值。

真实导航启用前必须保持以下限制：

```text
max_speed <= 0.05 m/s
max_yaw_rate <= 10 deg/s
localization confidence >= 0.80
odom timeout <= 0.25 s
local path timeout <= 0.50 s
```

## 7. 常见问题

- `Docker daemon is not accessible`：完成第 2.1 节并重新登录。
- CMake 找不到 `pcl_ros`：执行系统依赖阶段，确认 `ros-humble-pcl-ros` 已安装。
- `pyrealsense2` 导入失败：检查 `.env` 中 `REALSENSE_PYTHONPATH`，不要让 `/opt/ros/humble` 的 Python 3.10 包污染 uv Python 3.12。
- D435i 无权限：安装 udev 规则、拔插设备，再用当前用户测试。
- `/livox/lidar` 和 `/livox/imu` 都不存在：检查 `enx00e04c680d5f` 是否为 `192.168.200.1/24`、能否 ping 通 `192.168.200.20`，然后执行 `scripts/start_magic_mini_humble.sh restart`；不要用 Go2 的 `/utlidar/*` 代替，它当前没有有效数据。
- `/livox/lidar` 有数据但 FAST-LIO 无输出：先运行 DDS 字段验收，重点检查 `ring` 和相对纳秒 `time` 字段。
- 定位置信度低：先核对建图原点、传感器安装和地图摘要；最后才考虑重新建图。
- 启动时没有站立：检查 `eno1`、Go2 DDS、运动模式切换和启动日志；站立 hook 失败时主程序应中止。
- 导航目标已接受但机器人没有行走：检查两个实机门控、`/pathFollower` 的 `is_real_robot` 参数、定位状态及 watchdog 日志，不要绕过安全锁止。
