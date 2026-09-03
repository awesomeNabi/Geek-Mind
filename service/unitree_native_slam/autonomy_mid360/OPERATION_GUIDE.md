# 操作手册

### Step0: 预准备
1. 宿主机路径：cd /home/unitree/go2-fast-lio
2. 启动容器：docker start mid360_go2_nav_humble
3. 如果需要进容器执行ros命令：
docker exec -it mid360_go2_nav_humble bash
source /opt/ros/humble/setup.bash
source /workspace/nav_ws/install/setup.bash
source /workspace/autonomy-go2-mid360/workspace/install/setup.bash
## Step 1. FAST-LIO 建图
1. 宿主机终端执行：
```bash
bash nav_workspace/autonomy-go2-mid360/scripts/start_fastlio_unitree_autonomy_for_nav.sh \
  --output-dir /home/unitree/maps \
  --name autonomy_go2_mid360_company-test
```
交互：
```text
s  开始建图
q  保存地图并退出
```
## Step 1.1 建图可视化

环境：Foxglove。

连接：

```text
ws://<狗的IP>:9001
```


## Step 2. 建图重定位

重定位前启动Fast-lio 建图程序（同步骤1）：
```bash
bash nav_workspace/autonomy-go2-mid360/scripts/start_fastlio_unitree_autonomy_for_nav.sh \
  --output-dir /home/unitree/maps \
  --name <map_name>
```

### Step 2.1 启动重定位和规划
环境：宿主机，终端 2。

```bash
bash nav_workspace/autonomy-go2-mid360/scripts/start_nav.sh \
  --global-localization \
  --route-planner \
  --map-file /workspace/maps/<map_name>_<timestamp>.pcd \
  --no-real-robot \
  --auto-initialpose \
  --max-speed 0.2 \
  --max-yaw-rate 30.0 \
  --no-rviz
```
如果狗确定在建图起点附近，可以保留 `--auto-initialpose`。否则改用 `--no-auto-initialpose`，并在 Foxglove/RViz 里手动给接近当前位置的 `/initialpose`。



## Step 3. 采集和发布目标点

采集：ros2 topic echo --once /baselink2map

取输出里的：
```text
pose.pose.position.x
pose.pose.position.y
pose.pose.position.z
```

查看目标点：
```bash
ros2 topic echo --once /goal_point
```

发布目标点：

```bash
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh X Y Z
```

```bash
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --reset-graph X Y Z
```

`--reset-graph` 会先向 `/reset_visibility_graph` 发布一次 `std_msgs/msg/Empty`，等待 `/robot_vgraph` 重新变为非空，再发布新的 `/goal_point`。如果 FAR graph 重建较慢，可加长等待时间：

```bash
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --reset-graph --wait 40 X Y Z
```

强制切换到新目标：

```bash
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --force X Y Z
```

手动发布目标点，仅用于调试：

```bash
ros2 topic pub --once /goal_point geometry_msgs/msg/PointStamped \
"{header: {frame_id: map}, point: {x: X, y: Y, z: Z}}"
```

示例：

```bash
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh \
  -3.467642079644214 -2.586964652231151 0.4984068124813883
```
## 6-30 测试
起点 
[5.474314462770481, -2.0759878305262927, -0.34379825428205923, -0.007755049856628399, 0.013543442989985615, 0.6876094870463191, 0.725912961502662]
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --reset-graph --real-robot-ok 5.474314462770481 -2.0759878305262927 -0.34379825428205923
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --real-robot-ok 5.474314462770481 -2.0759878305262927 -0.34379825428205923

沙发：
ros2 topic pub --once /goal_point geometry_msgs/msg/PointStamped \
"{header: {frame_id: map}, point: { x: 4.631581484290042, y: -1.3085985848872264, z: -0.2902845431255161}}"

bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --reset-graph --real-robot-ok 4.631581484290042 -1.3085985848872264 -0.2902845431255161
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --real-robot-ok 4.631581484290042 -1.3085985848872264 -0.2902845431255161

工位边：
ros2 topic pub --once /goal_point geometry_msgs/msg/PointStamped \
"{header: {frame_id: map}, point: { x: -9.209053166999642, y: -1.6957972171725157, z: 1.0643356269382425}}"

bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --reset-graph --real-robot-ok -9.209053166999642 -1.6957972171725157 1.0643356269382425
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --real-robot-ok -9.209053166999642 -1.6957972171725157 1.0643356269382425

工位与展厅拐角：
      x: -15.446592716823343
      y: -0.49017753013916876
      z: 1.6794409362678302
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --reset-graph --real-robot-ok -15.446592716823343 -0.49017753013916876 1.6794409362678302
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --real-robot-ok -15.446592716823343 -0.49017753013916876 1.6794409362678302

展厅内部的具体位置：
x: -20.782451693868527
y: 5.638101075813721
z: 1.8

bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --reset-graph --real-robot-ok -20.782451693868527 5.638101075813721 1.8
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --real-robot-ok -20.782451693868527 5.638101075813721 1.8

展厅边空地：
ros2 topic pub --once /goal_point geometry_msgs/msg/PointStamped \
"{header: {frame_id: map}, point: {  x: -15.951452307880588,  y: 4.434339316010321, z: 1.6772551057986225}}"

bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --reset-graph --real-robot-ok -15.951452307880588 4.434339316010321 1.6772551057986225
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --real-robot-ok -15.951452307880588 4.434339316010321 1.6772551057986225

东侧工作区：
      x: 6.1904696135953206
      y: 24.396355920520957
      z: -0.31860461032207954
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --real-robot-ok 6.1904696135953206 24.396355920520957 -0.31860461032207954

机房
      x: -3.5488442063576637
      y: 26.743501420303204
      z: 0.5838668635211696
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --real-robot-ok -3.5488442063576637 26.743501420303204 0.5838668635211696

吧台
      x: -11.832858978247533
      y: 28.06862922047938
      z: 1.365568340092026
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --real-robot-ok -11.832858978247533 28.06862922047938 1.365568340092026
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --reset-graph --real-robot-ok -11.832858978247533 28.06862922047938 1.365568340092026

前台
      x: -14.600557879616547
      y: 17.247886817447778
      z: 1.6123827509159774
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --real-robot-ok -14.600557879616547 17.247886817447778 1.6123827509159774




## Step 4. 添加禁行区防止通过危险区域

## 4.1 导入预先加载的prior graph

docker exec -it mid360_go2_nav_humble bash -lc '
source /opt/ros/humble/setup.bash
source /workspace/autonomy-go2-mid360/workspace/install/setup.bash
ros2 topic pub --once /read_file_dir std_msgs/msg/String "{data: /workspace/autonomy-go2-mid360/workspace/prior_graphs/my_prior_graph_fianl.vgh}"
'

前提：

```text
Step 3 重定位和规划已经启动
localPlanner 正在运行
```

禁行区通过 `/navigation_boundary` 发布给 `localPlanner`：
`localPlanner` 最终按 `camera_init` 数值坐标使用边界。脚本支持两种输入：

```text
--frame camera_init  直接发布 camera_init 坐标
--frame map          输入 map 坐标，脚本读取 TF 后转换到 camera_init 再发布
```


## Step 4.2 使用 map 坐标添加禁行区 
### Note:边界点将按顺序连接(传入坐标的时候要么顺时针要么逆时针)

适合把禁行区作为场景标注保存下来。输入 `map` 坐标后，脚本会读取当前 TF，把点转换成 `camera_init` 后发布到 `/navigation_boundary`。

示例：

```bash
bash nav_workspace/autonomy-go2-mid360/scripts/publish_navigation_boundary.sh \
  --container mid360_go2_nav_humble \
  --frame map \
  --points "10.0,2.0,0; 11.0,2.0,0; 11.0,3.0,0; 10.0,3.0,0" \
  --repeat 5 \
  --rate 2
```

如果 TF 还没有准备好，可以加长等待时间：

```bash
bash nav_workspace/autonomy-go2-mid360/scripts/publish_navigation_boundary.sh \
  --container mid360_go2_nav_humble \
  --frame map \
  --points "10.0,2.0,0; 11.0,2.0,0; 11.0,3.0,0; 10.0,3.0,0" \
  --wait-tf 10 \
  --repeat 5 \
  --rate 2
```

读取当前机器人的 `camera_init` 坐标：

```bash
docker exec -it mid360_go2_nav_humble bash -lc \
  'source /opt/ros/humble/setup.bash; ros2 topic echo --once /state_estimation --field pose.pose.position'
```

读取当前机器人的 `map` 坐标：

```bash
docker exec -it mid360_go2_nav_humble bash -lc \
  'source /opt/ros/humble/setup.bash; ros2 topic echo --once /baselink2map --field pose.pose.position'
```

### 7-7 公司禁行区（6-30号的完整地图）
办公室走廊2：
  pose:
    position:
      x: 1.8767804353761415
      y: 4.127921029030081
      z: 0.026332603393748374
办公室走廊1：
    position:
      x: 1.8277126900639646
      y: 2.457399238569214
      z: -0.26026573844479095
工位过道：
  pose:
    position:
      x: -2.081056258170555
      y: -1.580222566242443
      z: 0.39943501287450583
工位区域-展厅边角：
  pose:
    position:
      x: -14.23652655966361
      y: 0.10343188596838332
      z: 1.558082286654045
工位区域1-展厅侧墙角：
x: -15.8449838157195
y: 0.9723376435321327
z: -0.5445926571880504

展厅门口：
  pose:
    position:
      x: -15.013158477197274
      y: 6.903468049960187
      z: 1.6250037558384887

机房饮水机拐角：
point:
  x: -11.847021621407087
  y: 27.574120166716575
  z: 0.0

工位区域2办公室口拐角：
    position:
      x: 5.216659234737864
      y: 24.36297925031263
      z: -0.21720462005681207

### 工位区域导航边界：
bash /home/unitree/go2-fast-lio/nav_workspace/autonomy-go2-mid360/scripts/publish_navigation_boundary.sh \
  --container mid360_go2_nav_humble \
  --frame map \
  --points "1.8767804353761415,4.127921029030081,0;1.8277126900639646,2.457399238569214,0; -2.081056258170555,-1.580222566242443,0; -14.23652655966361,0.10343188596838332,0; -15.013158477197274,6.903468049960187,0" \
  --wait-tf 10 \
  --repeat 10 \
  --rate 2

### 公司范围的导航边界：
bash /home/unitree/go2-fast-lio/nav_workspace/autonomy-go2-mid360/scripts/publish_navigation_boundary.sh \
  --container mid360_go2_nav_humble \
  --frame map \
  --points "1.8767804353761415,4.127921029030081,0.026332603393748374;1.8277126900639646,2.457399238569214,-0.26026573844479095;-2.081056258170555,-1.580222566242443,0.39943501287450583;-14.23652655966361,0.10343188596838332,1.558082286654045;-15.8449838157195,0.9723376435321327,-0.5445926571880504;-15.013158477197274,6.903468049960187,1.6250037558384887;-11.847021621407087,27.574120166716575, 0.0; 5.216659234737864,24.36297925031263,-0.21720462005681207" \
  --wait-tf 10 \
  --repeat 10 \
  --rate 2

## Step 5. 真机导航(替代step2的重定位)

```bash
bash nav_workspace/autonomy-go2-mid360/scripts/start_nav.sh \
  --global-localization \
  --route-planner \
  --map-file /workspace/maps/aaa-fuck-magic-company_20260630_100336.pcd \
  --real-robot \
  --max-speed 0.8 \
  --max-yaw-rate 80.0 \
  --auto-disarm-on-goal \
  --no-rviz
```

真机连续目标点测试时，发送新目标推荐使用：

```bash
bash nav_workspace/autonomy-go2-mid360/scripts/publish_goal.sh --reset-graph --real-robot-ok X Y Z
```
