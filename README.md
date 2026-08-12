# 小苏 · 公司内部 AI 助手

基于公司内部文档与系统的 AI 助手，通过钉钉提问即可获得带引用的回答；Web 后台管理文档与对话日志。

## 技术栈

- 后端：Python 3.11+ / FastAPI / uv
- 问答：OpenAI 兼容 API（DeepSeek 等）+ function calling
- 知识库：jieba 中文分词 + BM25 检索（本地 JSON 持久化，零外部服务）+ pypdf / python-docx（PDF/Word/MD/TXT）
- IM：钉钉官方 **Stream 模式**（长连接，无需公网 IP/域名）+ 飞书 **WebSocket 长连接**（无需公网 URL）+ 企业微信（可选回调适配）
- 前端：React + Vite（管理后台）
- MCP：fastmcp（Claude Desktop / Cursor 可调）

## 开源与参考声明

应用代码为原创；依赖、官方 SDK 与接口文档来源见 [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md)。

## 快速开始

1. 配置 `backend/.env`（复制 `.env.example`）：LLM API Key（可配多家供应商）、钉钉 AppKey/Secret
2. 安装依赖：`cd backend && uv sync`；前端 `cd web && pnpm install`
3. 启动：双击 `scripts/start.bat`（Windows），或 `sh scripts/start.sh`；前后端一起起可运行 `sh scripts/start_web.sh`
   - HTTP 服务：http://localhost:8000（接口文档 /docs）
   - 钉钉机器人：启动后自动连接，钉钉里 **@小苏** 提问即可（单聊/群聊都行）
   - 飞书机器人：启动后自动连接，飞书里 **@小苏** 提问即可（单聊/群聊都行）
4. 上传文档：`POST /api/docs`（或后台页面），之后即可问答

常用命令：`sh scripts/seed_data.sh` 生成并导入种子文档；`sh scripts/test.sh` 跑测试；`sh scripts/deploy.sh` 构建产物。

## 功能

- 文档知识库：上传/列表/删除（PDF/Word/MD/TXT），同名替换
- 智能问答：RAG 检索 + 引用来源（Web 可点击查看原文并高亮）+ 拒答 + 多轮（按用户隔离）+ 流式输出（Web SSE `/api/chat/stream`、钉钉 AI 卡片打字机、飞书 AI 卡片打字机）
- 文件上传问答：上传 Markdown/TXT/PDF/Word 后直接针对该文件提问，同样支持流式输出
- 工具调用：员工信息 / 考勤 / 销售订单 / 当前时间（mock 内部 API）
- IM 多端：钉钉 Stream + 飞书 WebSocket 长连接共用同一套问答引擎（企业微信回调适配也已提供）
- 对话日志：`/api/logs` 全量查看（含 Token / 成本 / 工具调用）
- 可观测性：`/api/traces` 记录每次问答/上传的耗时、Token、成本、工具与错误，后台可查看请求链路
- 错误容错：LLM 超时/限流自动重试，重试失败后降级为友好提示，不直接 500

## 测试

```bash
cd backend && uv run pytest tests/ -v   # 45 个用例，Mock LLM，不依赖真实 API
```

## 目录结构

```
backend/app/
├── knowledge/   文档解析 + 切块 + BM25 索引
├── agent/       问答核心（RAG + function calling）
├── tools/       工具注册与执行
├── mock_api/    内部系统 mock（员工/考勤/订单）
├── im/          钉钉 Stream 机器人
├── session/     多轮会话存储（SQLite）
├── mcp_server.py  MCP Server（Claude Desktop / Cursor 可调）
└── cost.py      Token 成本估算
```

## 钉钉集成（M4）

- 配置：`backend/.env` 里 `DINGTALK_APP_KEY` / `DINGTALK_APP_SECRET`
- 消息流：@小苏 → 去 @ → RAG/工具 → AI 卡片打字机回复（含引用来源；卡片失败自动回退文本）
- 流式卡片走钉钉 OpenAPI；卡片不可用时回退 session_webhook 文本回复

## 企业微信集成

- 配置：`backend/.env` 里 `WECOM_CORP_ID` / `WECOM_AGENT_ID` / `WECOM_SECRET` / `WECOM_TOKEN` / `WECOM_AES_KEY`
- 回调地址：`https://你的域名/api/im/wecom`，用于企业微信后台 URL 验证和消息接收
- 消息流：员工发消息 → 企业微信回调 → 小苏问答引擎 → 通过企业微信 API 主动回复（含引用来源）

## 飞书集成

- 配置：`backend/.env` 里 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`
- 接收方式：飞书官方 **WebSocket 长连接**，无需公网 URL、HTTPS、内网穿透
- 消息流：员工在飞书里 @小苏 → 长连接收到消息 → 小苏问答引擎 → AI 卡片打字机回复（含引用来源；卡片失败自动回退文本）

## Web 管理后台（M5）

- 技术：React 19 + Vite 6 + Tailwind v4
- 启动：双击 `scripts/start_web.bat`（自动起后端 + 前端，并打开浏览器 http://localhost:5173）
- 功能：文档上传/删除、备用聊天（含文件上传问答）、对话日志（含 Token/成本）、可观测性（请求链路）、设置（LLM 供应商切换、IM 状态）

## 系统架构

```
钉钉 App（私聊 / 群聊 @小苏）
   │  Stream 长连接（无需公网 IP/域名）
   ▼
钉钉适配层 im/ ──────────────► Agent 核心 agent/
                                    │
                 ┌──────────────────┼───────────────────┐
                 ▼                  ▼                   ▼
           knowledge/           tools/              session/
          文档→BM25 索引   mock API/时间工具   SQLite 多轮会话
                 │                  │                   │
                 └──────── LLM（OpenAI 兼容 API）◄───────┘
                                   ▲
   Web 管理后台（React+Vite）────► /api（FastAPI：docs/chat/logs）
```

## 加分项

### 多端 IM 接入

已接入 **钉钉 + 飞书**，两者共用同一套问答引擎、会话存储与可观测性；飞书采用 WebSocket 长连接，无需公网 URL。企业微信回调适配也已提供，可作为可选第三种接入。

### 多模型适配（≥2 家供应商）

内置 **DeepSeek / 智谱 GLM / 阿里通义** 3 家（OpenAI 兼容接口统一调用），默认由 `LLM_PROVIDER` 指定，也可在 Web 后台「设置」页**运行时切换**（内存生效，重启后恢复 .env 值）：

```bash
LLM_PROVIDER=deepseek        # deepseek / zhipu / dashscope
DEEPSEEK_API_KEY=sk-xxx
ZHIPU_API_KEY=xxx            # https://open.bigmodel.cn
DASHSCOPE_API_KEY=xxx        # https://dashscope.aliyuncs.com
```

未单独配置的供应商会回退到旧版 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`，老 .env 无需改动。

### Token 计数与成本展示

每次对话记录 usage（prompt / completion / total tokens），按模型公开单价估算成本；Web 后台「日志」页展示每轮 Token 数与成本，并提供汇总（总轮次 / 总 Token / 总成本）。

### MCP Server

把「小苏」的知识库问答与工具调用暴露为 MCP，可被 Claude Desktop / Cursor 调用：

```bash
uv run python -m app.mcp_server    # stdio 模式
```

Claude Desktop 配置（claude_desktop_config.json）：

```json
{
  "mcpServers": {
    "xiaosu": {
      "command": "uv",
      "args": ["--directory", "/path/to/xiaosu/backend", "run", "python", "-m", "app.mcp_server"]
    }
  }
}
```

暴露工具：`search_knowledge` / `ask_xiaosu` / `query_employee` / `query_attendance` / `query_orders` / `current_time`。

### Evals 自动化评测

26 条用例（文档命中 / 工具调用 / 多轮指代 / 拒答），跑出准确率：

```bash
uv run python scripts/eval.py            # 全量
uv run python scripts/eval.py --limit 5  # 快速试跑
```

报告写入 `logs/eval_report.json`（需配置真实 LLM API Key）。

## 验收对照（笔试 7.1-7.6）

| 验收点 | 实现 | 验证方式 |
|---|---|---|
| 7.1 基础问答带引用 | RAG 检索 + `[n]` 标注 + 📎 来源 | 钉钉问「员工每年几天年假？」 |
| 7.2 工具调用 | function calling 自主调 mock API | 钉钉问「员工 001 是哪个部门的？」 |
| 7.3 多轮对话 | 按 user+session 保存历史 | 先问「张伟」，再问「他上周来上班几天」 |
| 7.4 拒答 | 检索不到绝不编造 | 问「CEO 的家庭住址」 |
| 7.5 Key 失效兜底 | IM 返回友好错误 | `.env` 改错 Key 重启后提问 |
| 7.6 后台日志/文档管理 | Web 后台四页 | 浏览器 http://localhost:5173 |
