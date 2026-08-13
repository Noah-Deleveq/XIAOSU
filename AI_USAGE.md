# AI_USAGE.md —— 我是怎么用 AI 做这个项目的

> 本项目全程使用 **Claude Code**（终端里的 Claude）辅助开发。以下按笔试要求回答 5 个问题，最后附上完整的排障时间线（真实记录）。

## 1. 用了哪些 AI 工具？分别用在哪些环节？

| 环节 | 工具 | 怎么用的 |
|---|---|---|
| 架构与任务拆解 | Claude Code | 把笔试要求丢给它，让它按 M0-M6 里程碑拆任务（工程底座 → 知识库 → 问答 → 工具 → 钉钉 → Web 后台） |
| 代码生成 | Claude Code | 每个里程碑的骨架代码、接口、测试都由它生成，我再逐行 review 关键路径 |
| 排障 | Claude Code | 钉钉 SDK 不回复、消息被静默丢弃等问题，把日志和现象贴给它，让它给出排查方向 |
| 测试 | Claude Code + 人工 | 它生成 pytest 用例（Mock LLM），我补"模拟真实钉钉消息"的回归测试锁住踩过的坑 |
| 文档 | Claude Code | README 架构图、验收对照表、AI_USAGE 草稿 |

**原则：AI 写 80%，但"能跑起来"的标准由我把关**——每个模块都要求它能给我解释清楚，关键路径（拒答判定、function calling 消息流、钉钉 topic 注册）全部人工核实过。

## 2. 举一个具体的例子：prompt 是什么、哪里能用、哪里必须改？

**场景**：钉钉机器人"收到消息但不回复"（这是本项目最关键的调试过程，commit `82df8dd`）。

**我给 AI 的 prompt（大意）**：

> 钉钉 Stream 模式机器人已连上 wss 长连接，控制台没有任何报错，但私聊 @ 它完全没有回复。日志里也看不到消息进来。帮我排查。

**AI 给出的排查方向**（这条可用）：
- 检查 `register_callback_handler` 注册的 topic 是否和钉钉推送的 `headers.topic` 一致；
- 检查 handler 里是否抛了异常被 SDK 静默吞掉。

**AI 最初的代码（错）**：
```python
client.register_callback_handler("chatbot", XiaoSuBot())
```
它以为 topic 就是文档里说的 `"chatbot"`。结果钉钉推送的 `headers.topic` 实际是 `/v1.0/im/bot/messages/get`，永远匹配不上 → **每条消息被静默丢弃，窗口无任何日志**。

**我改的地方**：不信任"看起来对的用法"，直接翻钉钉 SDK 源码，发现官方常量 `ChatbotMessage.TOPIC` 才是真实值，改为：
```python
client.register_callback_handler(ChatbotMessage.TOPIC, XiaoSuBot())
```
**为什么必须改**：AI 是照着官方 README 的"示例"写的，但那个示例省略了真实 topic 值；只有源码里的常量才是运行时实际推送的值。

**后续锁死**：这条坑写进了回归测试 `test_im_topic.py`（断言注册用的是 `ChatbotMessage.TOPIC`），防止以后改代码再踩。

## 3. 有没有一次 AI 把我带沟里去的经历？怎么发现、怎么收拾的？

**有，而且不止一次，最典型的就是上面那个钉钉案例。** AI 在 `reply_text` 上也带我进过一次沟：

AI 生成 `msg.chatbot.reply_text(...)` 来回复消息——代码看起来完全符合官方示例，但 `ChatbotMessage` 是纯数据类，**根本没有 `chatbot` 属性**，一执行就抛 `AttributeError`，且被 SDK 静默吞掉（不回传也不报错）。我是在钉钉里实测发现"小苏收了消息却不回"后，逐层打日志排查出来的。

**怎么发现的**：
1. 钉钉真实发消息 → 无回复；
2. 后端控制台 → 无任何日志（异常被 SDK 吞了，说明问题出在 handler 内部）；
3. 在 handler 入口加 `logger` 打点 → 确认消息进来了，是回复那一步挂了；
4. 直接打印 `dir(msg)` → 发现根本没有 `chatbot` 属性。

**怎么收拾的**：改成 handler 自身的 `self.reply_text(text, msg)`（POST 消息自带 `session_webhook`，官方推荐用法），并写了一条**模拟真实钉钉消息走 process 全链路**的回归测试（`test_im.py`），保证这条路径永远被 CI 覆盖。

## 4. 我怎么验证 AI 生成的代码是对的？

四层验证，从快到慢：

1. **单元测试（Mock LLM，不依赖真实 API）**：`tests/` 里 45 条用例，用 FakeClient 替换 OpenAI client，覆盖知识库增删改、同名替换、拒答判定、工具调用循环、流式输出、钉钉 AI 卡片流式回复、引用定位、错误重试与降级、文件上传问答、可观测性、会话隔离、IM 运行开关与重复事件去重。本地 `uv run pytest tests/ -v` 全绿（实测 45 passed）。
2. **模拟真实消息的回归测试**：把踩过的坑（钉钉消息格式、topic 常量、reply 方式）固化成测试，防止 AI 后续改代码时把修好的 bug 改回来。
3. **真实 LLM 端到端**：连真实 DeepSeek API 跑 `scripts/qa_demo.py`，验证 RAG 引用格式、function calling 工具选择是否符合预期（commit `c61e0a2` 记录全量通过）。
4. **真实钉钉联调**：本地起 Stream 长连接，私聊实测 7.1-7.5 验收清单（年假、报销、工具调用、多轮指代、拒答、Key 失效兜底），确认机器人在真实环境可用。

**关键习惯**：AI 每生成一段代码，我先问它"这里为什么这样写"，它解释不清楚的地方一律人工重写；凡是它说"应该能跑"但没验证过的，必须落到测试或真实联调里。

## 5. 如果让我再做一遍，会怎么调整 AI 的使用方式？

1. **测试先行**：这次很多坑（钉钉 SDK、同名替换）是"写完代码→联调→发现 bug→补测试"的顺序。重做的话，先让 AI 按验收清单写好测试（Mock LLM 的 7.1-7.6 用例），再实现功能，让测试逼着行为正确，而不是靠人肉联调发现。
2. **更早锁定第三方 SDK 的真相**：钉钉 Stream SDK 文档和实际行为不一致，浪费了大半天。重做时第一步就让 AI 去读 SDK 源码确认 topic 常量、消息结构，而不是照 README 示例写。
3. **更细的 commit 粒度**：本次 debug 过程有几个 commit 是"修复+补测试"混在一起。重做的话拆成"复现问题的测试"和"修复"两个 commit，评审时更清楚。
4. **让 AI 多写"为什么"注释**：AI 写的代码注释偏少，很多设计决策（比如为什么用 BM25 不用向量库、为什么 session 按 user+conversation 双维度）是我后来补的文档。重做时要求它关键决策都写进注释或 ADR。

---

## 附：排障时间线（真实记录）

### 2026-08-12 会话（M3 工具调用 + M4 钉钉集成）

- **工具调用**：function calling 循环（`app/agent/qa.py::_call_llm_with_tools`）+ 4 个工具（员工/考勤/订单/当前时间）+ mock 内部 API（`app/mock_api/`）
- **钉钉 Stream**：调研官方 SDK 时踩了 3 个坑（都是文档没写清的）：
  1) websockets 17 与 SDK 不兼容（`exceptions` 子模块不再自动导入）→ 加 `import websockets.exceptions` 兼容；
  2) `register_callback_handler` 的 topic 必须是字符串 `ChatbotMessage.TOPIC`，传 `"chatbot"` 会导致消息全部匹配不上被静默丢弃；
  3) handler 参数要传**实例**不是类（`XiaoSuBot()`），否则 `pre_start() missing self`。
- **验证**：钉钉 Stream 真实连上 `wss://wss-open-connection-union.dingtalk.com:443/connect`，机器人已上线可收消息。

### 2026-08-12 会话（钉钉联调排障 + M5 Web 后台）

- **排障记录（本项目最关键的调试过程）**：私聊实测发现「小苏收到消息但不回复」，逐层排查出两个 SDK 误用：
  1) 用了 `msg.chatbot.reply_text()` → `ChatbotMessage` 是纯数据类、**根本没有 `chatbot` 属性**，一执行就 AttributeError 且被 SDK 静默吞掉 → 改为 handler 自身的 `self.reply_text(text, msg)`（POST 消息自带 session_webhook）；
  2) 注册 topic 传了字符串 `"chatbot"` → 钉钉推送消息的 `headers.topic` 实际是 `/v1.0/im/bot/messages/get`，永远匹配不上 → **每条消息被静默丢弃**（窗口无任何日志）→ 改用官方常量 `ChatbotMessage.TOPIC`。
  - 教训：SDK「看起来对的用法」可能全错，必须以源码/官方常量为准，并写回归测试锁死（模拟真实钉钉消息走 process 全链路）。
- **Web 管理后台（M5）**：React 19 + Vite 6 + Tailwind v4（`@tailwindcss/vite` 插件）；四页（文档/聊天/日志/设置）；vite proxy `/api → :8000` 联调。
- 环境坑：npm 11 默认阻止依赖 postinstall（esbuild `allow-scripts` 警告）——不影响构建（二进制走 optionalDependencies）；PowerShell `Copy-Item` 目录复制到已存在目标会整体嵌套。
