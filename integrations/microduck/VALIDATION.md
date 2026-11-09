# 本服务器验收记录

## 2026-11-09：仓库内源码发布验证

从 `Geek-Mind/integrations/microduck/` 直接启动，复用相邻的 MAGIC 和 Microduck 环境。默认依赖路径适配仓库目录结构，ROS 辅助启动脚本随模块分发。

- `bash run.sh test`：**23 passed**。
- `bash run.sh smoke --nav`：**通过**。使用本机固定模型响应，经过真实 MAGIC 规划/执行内核、MCP、MuJoCo 和 Nav2；五步动作全部 `SUCCEEDED`，7 个 MCP 工具可用，图像返回成功，额外 30° 转向成功，行走及导航取消均为 `CANCELLED`。
- 北侧走廊到达误差约 **0.221 米**，小于 0.3 米容差。本次重新验证未调用外部模型 API；先前的真实模型验收记录保留在下面。
- `chat --plain --no-browser` 从新目录启动公寓仿真与观察器，状态进入 `READY`，两路 640×360 画面持续更新；`/quit` 后退出码 0，自己启动的桥接与观察服务端口均关闭。
- Ruff 检查及格式检查、Python 编译、Shell 和观察页面 JavaScript 语法检查通过。网站构建及 lint 通过。
- 源码清单不包含 `.env`、日志、数据库、虚拟环境或权重；配置模板使用可替换路径。

本地证据：`.runtime/smoke-c5abdcdc/result.json` 与 `.runtime/import-viewer-check/result.json`，不随源码发布。测试使用 ROS 域 85/90 和独立端口，结束后关闭测试服务。

## 2026-11-09：交互控制台与实时双视角

入口：`bash run.sh chat`。全屏终端与 `--plain` 逐行模式均实际运行。

- **23 项自动化测试通过**：包含原有测试、新增的执行中取消、提交后立即取消、后续动作阻断、中文编辑/历史输入、视频过期、只读 HTTP 页面与事件持久化。
- 使用 MAGIC 现有真实模型，在终端输入“向左转20度，然后坐下，再站起来”，三个动作均成功；全屏终端中输入“坐下，然后站起来”也成功。
- “向前走2米，然后坐下”执行期间输入 `/stop`：行走最终 `CANCELLED`，后续坐下没有执行。规划期间立即停止：没有下发动作。
- 真实 Chrome 检查两路 640×360 图像均加载，任务与事件显示正常，没有 JavaScript 异常。第三人称视角清晰展示机器人本体，内墙仅在该视角透明显示。
- 最终自动验收连续观察约 5 秒，两路各采到 **15 个不同帧**，最大帧龄分别约 **0.569 / 0.454 秒**；纯观看新增截图数量为 **0**。
- 最终运行公开 `chat` 入口并输入 `/demo`，五个节点全部成功；输入 `/quit` 后 **2.67 秒**退出，退出码为 **0**。
- `ruff check`、`ruff format --check`、Python 编译检查、Shell 与页面 JavaScript 语法检查通过。

最终本地记录：`.runtime/console-final/result.json`、`.runtime/console-final/terminal.log`（不随源码分发）。公开界面截图：[interactive-preview.png](../../docs/assets/microduck-interactive-preview.png)。

真实模型和取消测试记录分别保存在 `.runtime/interactive-check/console-fc34465b/` 与 `.runtime/interactive-check/console-9f89f38c/` 的 `events.jsonl`、计划和执行结果文件中。以上测试使用独立 ROS 域 87/88 及端口，未将测试服务常驻。

实现中额外处理了：后台子进程脱离终端输入以避免退出延迟；软件渲染关闭阴影与多重采样；断线时显式显示离线；页面会话重启后重建视频连接和事件序列。

## 2026-11-08：基础控制链路

日期：2026-11-08。环境：Ubuntu 22.04.5 x86_64；MAGIC Python 3.11.14，MCP SDK 2.3.0，OpenAI SDK 1.60.1；ROS 使用相邻 Microduck 项目的 Pixi 环境，无桌面窗口。

## 自动化检查

`bash run.sh test`：**16 passed**。覆盖参数边界、重复指令、并发动作互斥、取消、重启后的 UNKNOWN 屏障、真实 MAGIC 任务内核的顺序执行与失败阻断、MCP SDK schema 兼容、独占任务运行器和模型计划格式约束。

`ruff check src tests scripts`、`ruff format --check src tests scripts`、`bash -n run.sh` 均通过。

## 真实模型与真实仿真

执行：`bash run.sh smoke --nav --live-llm`，退出码 **0**。

- 使用 MAGIC 现有模型配置，真实调用 `OpenAILLM` 和 `TaskPlanner`。
- 使用真实 `TaskRuntime`、`ExecutionGateway`、`MCPClientManager`，通过本项目 MCP/ROS 桥执行。
- MuJoCo 公寓场景、官方 v8 行走策略、原有坐下/站立策略、Nav2 和相机均实际启动。
- ROS 域 `85`，HTTP 端口 `8767`。

| 验收项 | 观测结果 |
| --- | --- |
| 原始自然语言目标 | 向前走15厘米，然后坐下、站起来，最后向左看并拍照 |
| 模型计划与任务执行 | 5 个节点均 `SUCCEEDED`，任务 `SUCCEEDED` |
| 行走 | 观测沿初始方向前进约 0.151 米，然后停止 |
| 坐下、站立 | 观测 `sit`、`rise → walk` 策略状态转换 |
| 转头 | 指令发送成功；未验证最终头部关节姿态 |
| 拍照 | 保存 640×360 JPEG；MCP 返回 image 内容块 |
| 额外 30 度转向 | 实测累计转角约 0.563 rad，动作 `SUCCEEDED` |
| 行走取消 | `CANCELLED`，确认停止后结束 |
| 北侧走廊导航 | 目标 (−0.18, 1.145)，最终 (−0.107, 0.928)，误差约 0.229 米；Nav2 与桥接器均成功 |
| 厨房导航取消 | `CANCELLED`，收到取消结果并确认停止 |
| MCP 工具发现 | 7 个工具可调用 |

完整本地记录：`.runtime/smoke-07e204eb/result.json`（不随源码分发）。任务编号：`b12f38895c5645b9b850edd6f50c0181`。同目录保存 `sim.log`、`bridge.log`、任务/动作 SQLite 数据库与相机图像。

## 用户入口

使用独立 ROS 域 `86`、端口 `8768` 启动公开命令 `bash run.sh up`，等待公寓导航就绪后执行 `bash run.sh demo`，演示成功退出。随后向启动器发送 SIGINT，仿真与桥接器正常关闭。

本地记录：`.runtime/acceptance/launcher.log`、`.runtime/acceptance/demo.log`（不随源码分发）。

## 为运行完成的兼容处理

1. MAGIC Python 与 ROS Python 分进程，通过本机 HTTP 连接。
2. 在项目内适配 MCP SDK 的 `inputSchema` / `input_schema` 字段差异。
3. 为 MAGIC 通用规划工具补齐节点字段与原始目标枚举约束；不放行修改用户目标或格式错误的计划。
4. 关闭本命令行入口不需要的 MAGIC 头像状态管理，避免遗留 Zenoh 线程阻塞进程退出。
5. ROS 使用单线程回调执行器，HTTP 和运动控制在独立线程中，解决多线程回调调度下的观测滞后。
6. 将官方 v8 行走权重固定下载到本项目，并校验 SHA256；覆盖导航转向加速度，解决旧版权重及初始转向命令死区问题。原项目权重与参数文件保留。

## 验收边界

这是仿真验收。未连接实体硬件；未验证踢球、翻滚、捡拾策略的任务效果，未验证视觉语义识别，也未遍历所有房间路线。导航到达容差为 0.3 米。训练策略的 Trigger 服务不支持中途取消；相关限制见 README。

`.runtime` 和 `.assets` 为本地运行产物，已加入忽略列表。复制源码时需重新准备权重与运行验收，不能把本记录当作其他机器的执行结果。
