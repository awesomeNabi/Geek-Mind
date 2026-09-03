# MAGIC_MINI Mid360 建图、重定位与导航操作指南

本文档适用于当前 MAGIC_MINI 仓库中的 Mid360 导航服务，涵盖：

- 启动 Mid360 驱动和 Docker 容器
- 启动 FAST-LIO 建图并保存 PCD 地图
- 使用已有 PCD 地图启动重定位和 FAR 导航
- 读取机器人当前位置及订阅 Foxglove 点选位置
- 安全发布导航目标并监听到达状态

当前默认运行环境：

| 项目 | 当前值 |
| --- | --- |
| MAGIC_MINI 根目录 | `/home/nvidia/MAGIC_MINI` |
| Docker 镜像 | `magic-mini-mid360-nav:humble` |
| Docker 容器 | `magic_mini_mid360_nav` |
| 容器内 ROS 工作空间 | `/opt/unitree_native_slam` |
| 容器内地图目录 | `/workspace/maps` |
| 容器内服务目录 | `/workspace/unitree_native_slam` |
| Foxglove 端口 | `9001` |

> **安全警告：** 真机导航前必须清空机器人周围区域，确认急停可用，并安排人员随时接管。只有明确希望机器人运动时，才可使用 `--real-robot` 和 `--real-robot-ok`。

## 1. 基础环境

以下宿主机命令默认从 MAGIC_MINI 根目录执行：

```bash
cd /home/nvidia/MAGIC_MINI
```

### 1.1 启动 Mid360 驱动和导航容器

推荐使用当前仓库的统一启动脚本：

```bash
bash scripts/start_magic_mini_humble.sh start
```

该命令会：

1. 启动宿主机 `/home/nvidia/ws_mid360` 中的 Livox 驱动。
2. 等待 `/livox/lidar` 和 `/livox/imu` 收到数据。
3. 启动名为 `magic_mini_mid360_nav` 的 Docker 容器。

查看当前状态：

```bash
bash scripts/start_magic_mini_humble.sh status
```

如果 Mid360 驱动已由其他程序启动，只需要启动导航容器：

```bash
bash service/unitree_native_slam/autonomy_mid360/scripts/run_container.sh
```

### 1.2 进入容器执行 ROS2 命令

```bash
docker exec -it magic_mini_mid360_nav bash
```

进入容器后加载环境：

```bash
source /opt/ros/humble/setup.bash
source /opt/unitree_native_slam/install/setup.bash
```

本文后续给出的 `docker exec ... bash -lc` 命令会自行加载上述环境，不需要提前进入容器。

## 2. 启动建图

当前 MAGIC_MINI 使用宿主机 Livox 驱动。FAST-LIO 使用 `/unitree/slam_lidar/points`，因此建图前需要启动 Livox 点云兼容桥。

### 2.1 终端 1：启动点云兼容桥

```bash
cd /home/nvidia/MAGIC_MINI

bash service/unitree_native_slam/autonomy_mid360/scripts/start_livox_compat_adapter.sh
```

兼容桥的数据流为：

```text
/livox/lidar
    ↓
/unitree/slam_lidar/points
```

保持该终端运行。

### 2.2 终端 2：启动 FAST-LIO 建图

```bash
cd /home/nvidia/MAGIC_MINI

bash service/unitree_native_slam/autonomy_mid360/scripts/start_fastlio_go2_livox_autonomy_for_nav.sh \
  --output-dir /home/nvidia/MAGIC_MINI/service/unitree_native_slam \
  --name company_map
```

出现交互提示后，使用以下按键：

```text
s  开始建图
q  保存地图、停止建图并退出
```

脚本会等待以下数据就绪：

- `/map_save`
- `/Odometry_loc`
- `/cloud_registered_1`

地图名称会自动附加时间戳，例如：

```text
company_map_20260718_153000.pcd
```

宿主机保存位置：

```text
/home/nvidia/MAGIC_MINI/service/unitree_native_slam/company_map_20260718_153000.pcd
```

容器内对应位置：

```text
/workspace/maps/company_map_20260718_153000.pcd
```

按下 `q` 后，必须确认终端输出以下信息，并确认文件非空：

```text
Saved final map:
```

地图保存完成后，在点云兼容桥终端按 `Ctrl+C`。

### 2.3 Foxglove 建图可视化

建图脚本默认启动 Foxglove Bridge。连接地址：

```text
ws://<MAGIC_MINI_IP>:9001
```

可重点查看：

- `/cloud_registered_1`
- `/Odometry_loc`
- `/Laser_map_1`
- `/path_1`

## 3. 启动重定位和导航

重定位使用 FAST-LIO 的实时里程计和点云作为 Open3D 全局定位输入。因此重定位期间，点云兼容桥和 FAST-LIO 都必须持续运行。

### 3.1 终端 1：启动点云兼容桥

```bash
cd /home/nvidia/MAGIC_MINI

bash service/unitree_native_slam/autonomy_mid360/scripts/start_livox_compat_adapter.sh
```

### 3.2 终端 2：启动 FAST-LIO 前端

```bash
cd /home/nvidia/MAGIC_MINI

bash service/unitree_native_slam/autonomy_mid360/scripts/start_fastlio_go2_livox_autonomy_for_nav.sh \
  --no-foxglove
```

出现提示后按 `s`，并保持该终端运行。

这里使用 `--no-foxglove`，由后续导航进程统一启动 9001 端口，避免两个 Foxglove Bridge 争用同一个端口。

重定位结束时在该终端按 `Ctrl+C`，不要按 `q`；`q` 会额外保存一份地图。

### 3.3 终端 3：启动无真机运动验证

第一次运行或更换地图后，建议先使用 `--no-real-robot` 验证重定位和规划链路。将 `<map_file>` 替换为实际地图文件名：

```bash
cd /home/nvidia/MAGIC_MINI

bash service/unitree_native_slam/autonomy_mid360/scripts/start_nav.sh \
  --global-localization \
  --route-planner \
  --map-file /workspace/maps/company_map_20260718_232353.pcd \
  --no-real-robot \
  --auto-initialpose \
  --max-speed 0.2 \
  --max-yaw-rate 30.0 \
  --foxglove \
  --no-rviz
```

当前 `unitree_go2_koala_nav_vision_no_arm` 配置使用的公司地图是：

```text
/workspace/maps/aaa-fuck-magic-company_20260630_100336.pcd
```

### 3.4 启动真机导航

确认以下事项后，才能启动真机模式：

- `/baselink2map` 正常输出且位置合理。
- 地图与当前 FAST-LIO 外参配置一致。
- FAR Planner 和 V-Graph 已准备好。
- 机器人周围安全且急停可用。

真机启动命令：

```bash
cd /home/nvidia/MAGIC_MINI

bash service/unitree_native_slam/autonomy_mid360/scripts/start_nav.sh \
  --global-localization \
  --route-planner \
  --map-file /workspace/maps/company_map_20260718_232353.pcd \
  --real-robot \
  --auto-initialpose \
  --max-speed 0.6 \
  --max-yaw-rate 80.0 \
  --auto-disarm-on-goal \
  --foxglove \
  --no-rviz
```

`--auto-disarm-on-goal` 会在 `/far_reach_goal_status=true` 后发送停止命令并释放运动控制。

### 3.5 设置初始位姿

`--auto-initialpose` 默认发布以下地图位姿：

```text
x=0, y=0, z=0, yaw=0
```

只有机器人位于建图起点附近时才应使用该参数。

如果机器人不在建图起点附近，启动时改用：

```bash
--no-auto-initialpose
```

然后通过 Foxglove 或 RViz 向 `/initialpose` 发布接近机器人实际位置的 `geometry_msgs/msg/PoseWithCovarianceStamped`。

### 3.6 检查重定位结果

读取一次机器人在 `map` 坐标系中的完整位姿：

```bash
docker exec -it magic_mini_mid360_nav bash -lc '
source /opt/ros/humble/setup.bash
source /opt/unitree_native_slam/install/setup.bash
ros2 topic echo --once /baselink2map --field pose.pose
'
```

只读取位置：

```bash
docker exec -it magic_mini_mid360_nav bash -lc '
source /opt/ros/humble/setup.bash
source /opt/unitree_native_slam/install/setup.bash
ros2 topic echo --once /baselink2map --field pose.pose.position
'
```

如果无法收到 `/baselink2map`，不要发布真机导航目标。

## 4. 加载 Prior Graph

当前完整 MAGIC 配置会在生命周期 Hook 中自动加载：

```text
/workspace/unitree_native_slam/prior_graphs/my_prior_graph_final.vgh
```

如果是手工启动 `start_nav.sh`，可以手动发布加载命令：

```bash
docker exec -it magic_mini_mid360_nav bash -lc '
source /opt/ros/humble/setup.bash
source /opt/unitree_native_slam/install/setup.bash
ros2 topic pub --once /read_file_dir std_msgs/msg/String \
"{data: /workspace/unitree_native_slam/prior_graphs/my_prior_graph_final.vgh}"
'
```

检查解码图和机器人 V-Graph：

```bash
docker exec -it magic_mini_mid360_nav bash -lc '
source /opt/ros/humble/setup.bash
source /opt/unitree_native_slam/install/setup.bash
ros2 topic echo --once /robot_vgraph --field size
'
```

`size` 必须为非零值。发布导航目标前，推荐使用第 6.1 节的只读就绪检查做最终确认。

## 5. 订阅和采集指定点

### 5.1 采集机器人当前地图坐标

让机器人移动到需要记录的位置，然后执行：

```bash
docker exec -it magic_mini_mid360_nav bash -lc '
source /opt/ros/humble/setup.bash
source /opt/unitree_native_slam/install/setup.bash
ros2 topic echo --once /baselink2map --field pose.pose
'
```

导航目标使用：

```text
pose.pose.position.x
pose.pose.position.y
pose.pose.position.z
```

如果需要记录完整地点位姿，还应保存：

```text
pose.pose.orientation.x
pose.pose.orientation.y
pose.pose.orientation.z
pose.pose.orientation.w
```

point1：
bash service/unitree_native_slam/autonomy_mid360/scripts/publish_goal.sh \
  --real-robot-ok \
  --reset-graph \
  13.274473422798136 -13.292993103591586 -0.4182117107770331

 point2：

  bash service/unitree_native_slam/autonomy_mid360/scripts/publish_goal.sh \
    --real-robot-ok \
    --reset-graph \
    19.125299735217556 -12.38291914142668 -0.8667006504281751

  point3：

  bash service/unitree_native_slam/autonomy_mid360/scripts/publish_goal.sh \
    --real-robot-ok \
    --reset-graph \
    13.249876151001878 -16.375615122695756 -0.4095210795088494

  point4：

  bash service/unitree_native_slam/autonomy_mid360/scripts/publish_goal.sh \
    --real-robot-ok \
    --reset-graph \
    6.820352528763857 -26.806587345314625 0.14692875035324077

  point5：

  bash service/unitree_native_slam/autonomy_mid360/scripts/publish_goal.sh \
    --real-robot-ok \
    --reset-graph \
    2.854579317381256 -27.675665160756868 0.4318887301458818

  point6：

  bash service/unitree_native_slam/autonomy_mid360/scripts/publish_goal.sh \
    --real-robot-ok \
    8.962587408160266 -17.375471916386477 -0.0935217192790602
### 5.2 订阅 Foxglove 点选位置

先启动订阅：

```bash
docker exec -it magic_mini_mid360_nav bash -lc '
source /opt/ros/humble/setup.bash
source /opt/unitree_native_slam/install/setup.bash
ros2 topic echo /clicked_point geometry_msgs/msg/PointStamped
'
```

然后在 Foxglove 中点选目标位置，读取：

```text
point.x
point.y
point.z
```

确保点选工具使用 `map` 坐标系。

### 5.3 监听实际发布的目标

```bash
docker exec -it magic_mini_mid360_nav bash -lc '
source /opt/ros/humble/setup.bash
source /opt/unitree_native_slam/install/setup.bash
ros2 topic echo /goal_point
'
```

## 6. 发布导航命令

推荐使用 `publish_goal.sh`。该脚本会检查容器、重定位、FAR Planner、V-Graph、活动目标以及真机运动许可。

### 6.1 只检查导航是否就绪

真机导航栈使用：

```bash
cd /home/nvidia/MAGIC_MINI

bash service/unitree_native_slam/autonomy_mid360/scripts/publish_goal.sh \
  --check-only \
  --real-robot-ok \
  0 0 0
```

`--check-only` 不会发布目标，也不会触发运动。

### 6.2 无真机模式发布目标

```bash
bash service/unitree_native_slam/autonomy_mid360/scripts/publish_goal.sh X Y Z
```

### 6.3 真机模式发布目标

```bash
bash service/unitree_native_slam/autonomy_mid360/scripts/publish_goal.sh \
  --real-robot-ok \
  X Y Z
```

`--real-robot-ok` 表示明确允许真机运动。只有已经确认目标点、地图、重定位和现场安全时才可添加。

### 6.4 重置 FAR 图并发布目标

首次加载 prior graph、FAR 图状态异常或需要清理旧规划状态时使用：

```bash
bash service/unitree_native_slam/autonomy_mid360/scripts/publish_goal.sh \
  --reset-graph \
  --real-robot-ok \
  --wait 40 \
  X Y Z
```

该命令会：

1. 向 `/reset_visibility_graph` 发布重置消息。
2. 重新加载 `my_prior_graph_final.vgh`。
3. 等待 `/decoded_vgraph` 和 `/robot_vgraph` 恢复。
4. 发布 `/goal_point`。
5. 验证 `/way_point_global`、`/way_point` 和规划路径。

无真机模式使用时删除 `--real-robot-ok`。

### 6.5 强制替换正在执行的目标

默认情况下，脚本检测到活动目标时会拒绝覆盖。确认需要中断原目标后，可以使用：

```bash
bash service/unitree_native_slam/autonomy_mid360/scripts/publish_goal.sh \
  --force \
  --real-robot-ok \
  X Y Z
```

### 6.6 直接发布 ROS2 目标，仅用于调试

以下命令会绕过仓库脚本提供的真机许可、重定位、V-Graph 和活动目标检查：

```bash
docker exec -it magic_mini_mid360_nav bash -lc '
source /opt/ros/humble/setup.bash
source /opt/unitree_native_slam/install/setup.bash
ros2 topic pub --once /goal_point geometry_msgs/msg/PointStamped \
"{header: {frame_id: map}, point: {x: X, y: Y, z: Z}}"
'
```

真机上应优先使用 `publish_goal.sh`。

## 7. 监听导航状态

### 7.1 监听到达状态

```bash
docker exec -it magic_mini_mid360_nav bash -lc '
source /opt/ros/humble/setup.bash
source /opt/unitree_native_slam/install/setup.bash
ros2 topic echo /far_reach_goal_status
'
```

看到以下内容表示 FAR Planner 判断已经到达目标：

```text
data: true
```

### 7.2 查看全局和局部航点

全局航点：

```bash
docker exec -it magic_mini_mid360_nav bash -lc '
source /opt/ros/humble/setup.bash
source /opt/unitree_native_slam/install/setup.bash
ros2 topic echo /way_point_global
'
```

转换到局部规划坐标系后的航点：

```bash
docker exec -it magic_mini_mid360_nav bash -lc '
source /opt/ros/humble/setup.bash
source /opt/unitree_native_slam/install/setup.bash
ros2 topic echo /way_point
'
```

## 8. 一体化启动完整 MAGIC 导航栈

如果需要按照当前 `unitree_go2_koala_nav_vision_no_arm` 配置启动完整系统，包括：

- 宿主机 Mid360 驱动
- Docker 容器
- Livox 点云兼容桥
- FAST-LIO
- Open3D 全局重定位
- FAR Planner
- Prior graph
- 导航边界
- MAGIC 语音和 Agent

执行：

```bash
cd /home/nvidia/MAGIC_MINI

KOALA_FETCH_CONFIG=unitree_go2_koala_nav_vision_no_arm \
  bash scripts/start_magic_mini_humble.sh start

KOALA_FETCH_CONFIG=unitree_go2_koala_nav_vision_no_arm \
  bash scripts/start_magic_mini_humble.sh start-agent
```

一体化方式和第 3 节的手工启动方式二选一，不要重复启动兼容桥、FAST-LIO 或 Nav 实例。

查看状态：

```bash
bash scripts/start_magic_mini_humble.sh status
```

连接 Agent 日志：

```bash
bash scripts/start_magic_mini_humble.sh attach
```

## 9. 停止服务

### 9.1 手工启动方式

按以下顺序停止：

1. 在 `start_nav.sh` 终端按 `Ctrl+C`，停止规划和真机命令发布。
2. 在 FAST-LIO 终端按 `Ctrl+C`。
3. 在点云兼容桥终端按 `Ctrl+C`。

如果基础设施由统一脚本启动，最后执行：

```bash
bash scripts/start_magic_mini_humble.sh stop
```

### 9.2 一体化启动方式

```bash
bash scripts/start_magic_mini_humble.sh stop
```

该命令会停止 MAGIC Agent、导航会话、受管 Mid360 驱动和导航容器。

## 10. 常见问题

### 10.1 容器未运行

错误示例：

```text
Container is not running: magic_mini_mid360_nav
```

处理：

```bash
bash scripts/start_magic_mini_humble.sh start
```

### 10.2 FAST-LIO 没有数据

检查：

```bash
bash service/unitree_native_slam/autonomy_mid360/scripts/check_topics.sh
```

重点确认：

- `/livox/lidar`
- `/livox/imu`
- `/unitree/slam_lidar/points`
- `/Odometry_loc`
- `/cloud_registered_1`

### 10.3 无法读取 `/baselink2map`

通常表示全局重定位尚未完成。检查：

- FAST-LIO 是否持续输出 `/Odometry_loc` 和 `/cloud_registered_1`。
- `--map-file` 是否存在于 `/workspace/maps`。
- 地图是否与当前 FAST-LIO 外参配置一致。
- 初始位姿是否接近机器人的真实位置。

### 10.4 目标被拒绝

如果提示已有活动目标：

- 等待当前目标完成；或
- 明确需要替换时使用 `--force`；或
- 需要清理 FAR 图时使用 `--reset-graph`。

如果提示真机控制未授权：

- 确认确实需要机器人运动后添加 `--real-robot-ok`。

### 10.5 Foxglove 端口冲突

FAST-LIO 和 Nav 都可以启动 Foxglove Bridge，默认端口均为 9001。重定位流程中应：

- FAST-LIO 使用 `--no-foxglove`。
- Nav 使用 `--foxglove`。

然后连接：

```text
ws://<MAGIC_MINI_IP>:9001
```
