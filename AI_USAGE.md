
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
