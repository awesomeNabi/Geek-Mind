# MAGIC_MINI 启动流程

> 本文是旧的 Go2 + ARX/Foxy 兼容流程。当前 `/home/nvidia` Ubuntu 22.04 + ROS 2 Humble 主机请使用 [HUMBLE_SETUP.md](HUMBLE_SETUP.md)，不要按本文启动 ARX。

本文档面向当前这台 Unitree Go2 + ARX X5 机器，说明首次部署、日常启动、检查与停止流程。

> 这是实机控制流程。启动前请确认机器人周围无人员和障碍物、急停可用、机械臂处于安全姿态，并确认 `UNITREE_ETHERNET` 指向机器人网口。

## 1. 选择导航模式

| 模式 | `KOALA_FETCH_CONFIG` | 导航实现 | 额外要求 |
| --- | --- | --- | --- |
| 原生模式（默认） | `unitree_go2_koala_fetch_single_mode` | Unitree 原生重定位与导航 | `/home/unitree/maps/kitchen_pro.pcd` |
| Mid360 模式 | `unitree_go2_koala_fetch_single_mode_autonomy_mid360` | 项目内置 FAST-LIO、定位和自主导航栈 | Mid360 Docker 镜像、驱动和场地地图 |

两种模式都保留当前组合动作：

- 启动整个配置时不会自动站起。
- 收到导航动作后，先检查地点、脚本和运行环境，再自动站起；站起成功后才发布导航目标。
- 收到抓取动作后，抓取前自动趴下。
- 关闭配置时不会额外执行自动趴下。

## 2. 首次部署的公共准备

进入项目目录：

```bash
cd /home/unitree/MAGIC_MINI
```

首次部署时创建环境文件；已有 `.env` 时不要覆盖：

```bash
test -f .env || cp .env.example .env
${EDITOR:-nano} .env
```

至少填写 `DASHSCOPE_API_KEY`。不要把真实密钥提交到 Git，也不要把包含密钥的 `.env` 发到日志中。

安装 Python 依赖并检查项目内文件：

```bash
uv sync --all-groups --extra dds --extra wake-word
uv run --extra dds tools/validate_magic_mini.py
```

验证器会区分两类结果：项目内部文件缺失会直接失败；外部绝对引用会被列出。列表同时包含主机文件、容器路径和 ROS 话题，只有主机文件路径需要在目标机器上实际存在。

## 3. Mid360 模式的一次性构建

只使用原生模式时跳过本节。Mid360 镜像只需首次部署或导航源码、依赖发生变化后重新构建。

### 3.1 构建镜像

可直接使用默认 ROS Humble 基础镜像：

```bash
bash service/unitree_native_slam/autonomy_mid360/scripts/build_image.sh
```

如果本机已有 `unitree_humble_dev:latest`，可避免从 Docker Hub 拉取默认基础镜像：

```bash
BASE_IMAGE=unitree_humble_dev:latest \
BUILD_JOBS=2 \
  bash service/unitree_native_slam/autonomy_mid360/scripts/build_image.sh
```

构建默认使用清华 TUNA 的 Ubuntu Ports、ROS 2 和 PyPI 镜像源。镜像源异常时可临时退回基础镜像原始软件源：

```bash
USE_TUNA_MIRROR=0 \
  bash service/unitree_native_slam/autonomy_mid360/scripts/build_image.sh
```

确认镜像存在：

```bash
docker image inspect magic-mini-mid360-nav:humble >/dev/null
```

### 3.2 构建可能卡住的位置

| 日志阶段 | 正在做什么 | 常见原因 |
| --- | --- | --- |
| `preflight 1/2` | 检查或拉取基础镜像 | Docker Hub 网络不可用或限流；TUNA 的 apt 源不能加速 Docker 镜像拉取 |
| `stage 2/6` | apt 和 ROS 2 软件包安装 | 镜像站连接、ROS 索引同步或大软件包下载较慢 |
| `stage 3/6` | Python 包安装 | PyPI 镜像连接异常 |
| `stage 4/6` | 编译 Livox-SDK2 | CPU 或内存压力 |
| `stage 5/6` | 编译完整 ROS 工作区 | 通常是最久阶段；若出现 `Killed`，多半是内存不足 |
| `stage 6/6` | 检查统一安装空间 | 前面的 colcon 构建没有生成完整的 `install/setup.bash` |

内存不足时降低并行度后重试：

```bash
BUILD_JOBS=1 \
  bash service/unitree_native_slam/autonomy_mid360/scripts/build_image.sh
```

### 3.3 检查实机外部资源

```bash
test -x /unitree/module/unitree_slam/bin/mid360_driver
test -s /home/unitree/maps/aaa-fuck-magic-company_20260630_100336.pcd
```

两个命令都应返回退出码 `0`。Mid360 场地地图不会被打包进 Git 仓库，需要单独复制到目标机器。

可提前创建并检查容器：

```bash
bash service/unitree_native_slam/autonomy_mid360/scripts/run_container.sh
docker exec magic_mini_mid360_nav \
  test -f /opt/unitree_native_slam/install/setup.bash
```

这一步不是每次启动都必须手工执行；统一启动脚本会自动创建或重新启动容器。

## 4. 日常启动

### 4.1 原生模式

```bash
cd /home/unitree/MAGIC_MINI
KOALA_FETCH_CONFIG=unitree_go2_koala_fetch_single_mode \
  scripts/start_magic_mini_stack.sh start
```

### 4.2 Mid360 模式

```bash
cd /home/unitree/MAGIC_MINI
KOALA_FETCH_CONFIG=unitree_go2_koala_fetch_single_mode_autonomy_mid360 \
  scripts/start_magic_mini_stack.sh start
```

Mid360 模式的实际启动顺序如下：

1. 检查 `tmux`、`uv`、Docker、机器人 SDK、配置、模型、驱动和地图。
2. 确保 `magic_mini_mid360_nav` 容器正在运行。
3. 创建 `magic_mini_stack` tmux 会话，并启动 `arx_ros2`、`arx_bridge`、`koala_fetch` 三个窗口。
4. `koala_fetch` 加载 Mid360 startup hook，启动 FAST-LIO 与导航 tmux 会话。
5. hook 等待关键 ROS 话题、定位、先验图和导航边界就绪；失败时中止主程序，不进入可导航状态。
6. 启动完成后机器人仍保持原姿态。第一次导航命令到来时，导航 action 才执行站起并发布目标。

startup hook 最长可能等待数十秒，这是导航栈初始化和健康检查时间，不是每次发布导航目标都会重复的延迟。

## 5. 查看状态和日志

查看主会话状态：

```bash
scripts/start_magic_mini_stack.sh status
```

进入主会话：

```bash
scripts/start_magic_mini_stack.sh attach
```

在 tmux 中使用 `Ctrl-b` 后按数字或窗口名切换窗口；使用 `Ctrl-b d` 退出查看，但保持服务运行。

Mid360 启动后可直接读取两个导航会话最近的输出：

```bash
tmux capture-pane -pt go2_fastlio_autonomy -S -100
tmux capture-pane -pt go2_mid360_autonomy_nav -S -100
```

检查关键话题和 TF：

```bash
bash service/unitree_native_slam/autonomy_mid360/scripts/check_topics.sh
bash service/unitree_native_slam/autonomy_mid360/scripts/check_tf_tree.sh
```

## 6. 停止与重启

直接停止主会话：

```bash
scripts/start_magic_mini_stack.sh stop
```

若希望给 Mid360 的 shutdown hook 留出完整清理时间，先向主程序发送 `Ctrl-C`，等待其退出，再停止外层会话：

```bash
tmux send-keys -t magic_mini_stack:koala_fetch C-c
scripts/start_magic_mini_stack.sh stop
```

当前配置的 `stop_container_on_shutdown` 为 `false`，因此停止 MAGIC 后 Docker 容器会保留，便于下次快速启动。需要完全停止时再执行：

```bash
docker stop magic_mini_mid360_nav
```

重启当前所选模式：

```bash
scripts/start_magic_mini_stack.sh restart
```

注意：`restart` 会重新读取 `.env`。如果本次模式是通过命令行临时指定的，重启时也应再次带上相同的 `KOALA_FETCH_CONFIG`。

## 7. 常见失败判断

- 提示 `DASHSCOPE_API_KEY is not set`：补全 `.env` 后重启。
- 提示地图或 Mid360 驱动缺失：把对应外部文件放到配置要求的绝对路径。
- 提示 Docker 镜像缺失：先执行第 3 节的镜像构建。
- startup hook 超时或中止：先查看两个 Mid360 tmux 会话，再运行话题与 TF 检查脚本。
- 导航目标没有发布：查看主程序日志；地点不存在、容器/脚本检查失败或站起失败都会主动阻止目标发布。
- colcon 阶段出现 `Killed`：用 `BUILD_JOBS=1` 重建。
