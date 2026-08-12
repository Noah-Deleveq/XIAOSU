# 小苏 · 公司内部 AI 助手

基于公司内部文档与系统的 AI 助手，通过钉钉提问即可获得带引用的回答；Web 后台管理文档与对话日志。

## 技术栈

- 后端：Python 3.11+ / FastAPI / uv（禁 pip）
- 问答：OpenAI 兼容 API（DeepSeek 等）+ function calling
- 知识库：ChromaDB（本地向量库）+ pypdf / python-docx（PDF/Word/MD/TXT）
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
cd backend && uv run pytest tests/ -v   # 11 个用例，Mock LLM，不依赖真实 API
```

## 目录结构

```
backend/app/
├── knowledge/   文档解析 + 切块 + Chroma 索引
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
