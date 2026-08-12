
### 2026-08-12 会话（M3 工具调用 + M4 钉钉集成）

- **工具调用**：function calling 循环（）+ 4 个工具（员工/考勤/订单/当前时间）+ mock 内部 API（）
- **钉钉 Stream**：调研官方 SDK 时踩了 3 个坑（都是文档没写清的）：
  1) websockets 17 与 SDK 不兼容（ 子模块不再自动导入）→ 加  兼容；
  2)  的 topic 必须是字符串 ，传类会导致 json 序列化报错 ；
  3) handler 参数要传**实例**不是类（），否则 。
- **验证**：钉钉 Stream 真实连上 ，机器人已上线可收消息。

### 2026-08-12 会话（M3 工具调用 + M4 钉钉集成）

- **工具调用**：function calling 循环（`app/agent/qa.py::_call_llm_with_tools`）+ 4 个工具（员工/考勤/订单/当前时间）+ mock 内部 API（`app/mock_api/`）
- **钉钉 Stream**：调研官方 SDK 时踩了 3 个坑（都是文档没写清的）：
  1) websockets 17 与 SDK 不兼容（`exceptions` 子模块不再自动导入）→ 加 `import websockets.exceptions` 兼容；
  2) `register_callback_handler` 的 topic 必须是字符串 `"chatbot"`，传类会导致 json 序列化报错 `Object of type type is not JSON serializable`；
  3) handler 参数要传**实例**不是类（`XiaoSuBot()`），否则 `pre_start() missing self`。
- **验证**：钉钉 Stream 真实连上 `wss://wss-open-connection-union.dingtalk.com:443/connect`，机器人已上线可收消息。

### 2026-08-12 会话（钉钉联调排障 + M5 Web 后台）

- **排障记录（本项目最关键的调试过程）**：私聊实测发现「小苏收到消息但不回复」，逐层排查出两个 SDK 误用：
  1) 用了 `msg.chatbot.reply_text()` → `ChatbotMessage` 是纯数据类、**根本没有 `chatbot` 属性**，一执行就 AttributeError 且被 SDK 静默吞掉 → 改为 handler 自身的 `self.reply_text(text, msg)`（POST 消息自带 session_webhook）；
  2) 注册 topic 传了字符串 `"chatbot"` → 钉钉推送消息的 `headers.topic` 实际是 `/v1.0/im/bot/messages/get`，永远匹配不上 → **每条消息被静默丢弃**（窗口无任何日志）→ 改用官方常量 `ChatbotMessage.TOPIC`。
  - 教训：SDK「看起来对的用法」可能全错，必须以源码/官方常量为准，并写回归测试锁死（模拟真实钉钉消息走 process 全链路）。
- **Web 管理后台（M5）**：React 19 + Vite 6 + Tailwind v4（`@tailwindcss/vite` 插件）；四页（文档/聊天/日志/设置）；vite proxy `/api → :8000` 联调。
- 环境坑：npm 11 默认阻止依赖 postinstall（esbuild `allow-scripts` 警告）——不影响构建（二进制走 optionalDependencies）；PowerShell `Copy-Item` 目录复制到已存在目标会整体嵌套。

