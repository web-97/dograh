# Dograh + Pipecat LiveKit 接入实现方案（扩展版）

本文档给出 Dograh 接入 LiveKit 的实现方案要点，聚焦“拨打电话 -> AI agent 加入 LiveKit room 对话”的整体流程与落地步骤，补充关键模块、接口与执行顺序。

## 目标

- 让电话呼入用户以 LiveKit participant 身份进入 room。
- 让 Pipecat AI agent 通过 LiveKitTransport 加入同一 room 并进行双向语音对话。
- 通过数据通道/事件回调管理 room 生命周期与会话流程。
- 将 Dograh 的会话管理、权限与审计对接 LiveKit 资源。

## 前置条件

- 已部署 LiveKit Server（自建或云端）。
- 已获取 `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` / `LIVEKIT_URL`。
- 具备 room 创建与 token 生成能力（通过 LiveKit API/SDK）。
- 已具备电话入口（SIP/PSTN 网关或既有运营商桥接服务）。

## 实现方案

### 1) 电话入口 -> LiveKit room

- 通过 LiveKit 的 SIP/PSTN 网关或现有电话桥接服务，将电话呼入接入到指定 LiveKit room。
- 该电话端在 LiveKit 中表现为一个 participant，成为对话的“用户侧”。
- 建议在 Dograh 侧先创建 room 并写入数据库，记录 `room_name`、`state`、`type`、`user_id` 等元数据，便于后续追踪。

### 2) AI agent 加入 room

- 使用 Pipecat 的 LiveKitTransport 连接到同一个 room。
- 运行时获取 `url` / `token` / `room_name`，并创建 transport 实例：
  - `LiveKitTransport(url, token, room_name, params=LiveKitParams(...))`
  - 开启 `audio_in_enabled` 与 `audio_out_enabled`，并配置 VAD 以管理对话轮次。

### 3) 对话流水线

将 LiveKitTransport 接入 Pipecat pipeline，实现端到端语音对话：

```
transport.input() -> STT -> LLM -> TTS -> transport.output()
```

- `transport.input()` 接收来自 LiveKit room 的音频。
- STT 负责语音转文本。
- LLM 生成响应。
- TTS 合成语音。
- `transport.output()` 将语音发送回 LiveKit room。

### 4) 事件与数据通道

- 使用 `on_first_participant_joined` 在用户入会时触发欢迎语或引导。
- 使用 `on_data_received` 处理来自房间的数据消息，并将其转成 Pipecat 的对话帧（例如 interruption/转写）。
- 监听 participant 离开事件，更新 Dograh 会话状态并释放资源。

### 5) Dograh 内部协同点

- **会话映射**：将通话会话 ID 与 `room_name`、LiveKit participant 映射。
- **权限控制**：token 生成与 Dograh 用户/组织权限绑定。
- **状态同步**：room 状态（活跃、结束、失败）与通话状态同步。
- **审计与追踪**：记录 join/leave、音频通道连接与异常事件。

### 6) 推荐实现顺序

1. 完成 LiveKit room 创建与 token 生成模块。
2. 在 Dograh API 中提供 room/session 创建接口并写入数据库。
3. 接入 LiveKitTransport，并跑通 pipeline：`transport.input()` -> STT -> LLM -> TTS -> `transport.output()`。
4. 接入 LiveKit 事件回调，处理入会/离会与数据通道消息。
5. 绑定电话入口到 room，确保拨打流程可触发 room 加入与 AI agent 启动。
6. 打通审计与监控埋点（通话时长、丢包、异常断开）。

## 交付物清单

- LiveKit room 创建与 token 生成模块。
- Pipecat LiveKitTransport 连接与 pipeline 组装。
- 事件与数据通道回调处理逻辑。
- Dograh 数据模型与会话追踪逻辑对接。
- 电话入口与 room 映射配置。

## 验收要点

- 电话呼入后，房间内出现电话 participant 与 AI agent participant。
- AI agent 可在房间内正常收发音频并完成对话。
- 关键事件（用户入会、断开、异常）可被后端捕获并记录。
- Dograh 内部会话记录与 LiveKit room 状态一致。
