# 小苏 · 公司内部 AI 助手

基于公司内部文档与系统的 AI 助手，通过钉钉提问即可获得带引用的回答；Web 后台管理文档与对话日志。

## 技术栈

- 后端：Python 3.11+ / FastAPI / uv（禁 pip）
- 问答：OpenAI 兼容 API（DeepSeek 等）+ function calling
- 知识库：jieba 中文分词 + BM25 检索（本地 JSON 持久化，零外部服务）+ pypdf / python-docx（PDF/Word/MD/TXT）
- IM：钉钉官方 **Stream 模式**（长连接，无需公网 IP/域名）
- 前端：React + Vite（管理后台）

## 快速开始

1. 配置 `backend/.env`（复制 `.env.example`）：LLM API Key、钉钉 AppKey/Secret
2. 安装依赖：`cd backend && uv sync`
3. 启动：双击 `scripts/start.bat`（Windows），或 `sh scripts/start.sh`
   - HTTP 服务：http://localhost:8000（接口文档 /docs）
   - 钉钉机器人：启动后自动连接，钉钉里 **@小苏** 提问即可（单聊/群聊都行）
4. 上传文档：`POST /api/docs`（或后台页面），之后即可问答

## 功能

- 文档知识库：上传/列表/删除（PDF/Word/MD/TXT），同名替换
- 智能问答：RAG 检索 + 引用来源 + 拒答 + 多轮（按用户隔离）
- 工具调用：员工信息 / 考勤 / 销售订单 / 当前时间（mock 内部 API）
- 对话日志：`/api/logs` 全量查看

## 测试

```bash
cd backend && uv run pytest tests/ -v   # 15 个用例，Mock LLM，不依赖真实 API
```

## 目录结构

```
backend/app/
├── knowledge/   文档解析 + 切块 + BM25 索引
├── agent/       问答核心（RAG + function calling）
├── tools/       工具注册与执行
├── mock_api/    内部系统 mock（员工/考勤/订单）
├── im/          钉钉 Stream 机器人
└── session/     多轮会话存储（SQLite）
```

## 钉钉集成（M4）

- 配置：`backend/.env` 里 `DINGTALK_APP_KEY` / `DINGTALK_APP_SECRET`
- 消息流：@小苏 → 去 @ → RAG/工具 → 回复（含引用来源）
- 回复走 session_webhook（官方 reply_text），无需额外权限配置

## Web 管理后台（M5）

- 技术：React 19 + Vite 6 + Tailwind v4
- 启动：双击 `scripts/start_web.bat`（自动起后端 + 前端，并打开浏览器 http://localhost:5173）
- 功能：文档上传/删除、备用聊天（浏览器直接对话，不依赖钉钉）、对话日志、服务状态
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

## 验收对照（笔试 7.1-7.6）

| 验收点 | 实现 | 验证方式 |
|---|---|---|
| 7.1 基础问答带引用 | RAG 检索 + `[n]` 标注 + 📎 来源 | 钉钉问「员工每年几天年假？」 |
| 7.2 工具调用 | function calling 自主调 mock API | 钉钉问「员工 001 是哪个部门的？」 |
| 7.3 多轮对话 | 按 user+session 保存历史 | 先问「张伟」，再问「他上周来上班几天」 |
| 7.4 拒答 | 检索不到绝不编造 | 问「CEO 的家庭住址」 |
| 7.5 Key 失效兜底 | IM 返回友好错误 | `.env` 改错 Key 重启后提问 |
| 7.6 后台日志/文档管理 | Web 后台四页 | 浏览器 http://localhost:5173 |

