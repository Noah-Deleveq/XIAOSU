# 小苏 · AI 助手笔试项目实施计划（PLAN）

> 对应笔试要求：公司内部 AI 助手「小苏」· 全栈 AI Coding 工程师
> 技术选型：**钉钉（Stream 模式）+ OpenAI 兼容 API + Python/FastAPI + React**

## 一、技术选型与理由

| 层 | 选型 | 理由 |
|----|------|------|
| 后端 | Python 3.11 + FastAPI + **uv**（`.venv`，禁 pip） | AI 生态最顺；uv 满足题目底线；Pydantic 强类型 |
| 前端后台 | React 19 + Vite + Tailwind v4（pnpm，ESM） | 后台功能少，轻量可控；满足题目版本底线 |
| LLM | OpenAI 兼容 API（openai SDK，base_url 可配） | DeepSeek/通义/GLM/OpenAI 都能用；function calling + 流式原生支持 |
| 向量库 | ChromaDB（本地持久化） | 免费、零运维、笔试数据量绰绰有余 |
| 文档解析 | pypdf（PDF）+ python-docx（Word）+ 原生（MD/TXT） | 覆盖题目要求的 4 种格式 |
| 钉钉集成 | 钉钉官方 **Stream 模式**（长连接 SDK） | 无需公网 IP/域名，本地就能跑，最适合笔试 Demo |
| Mock 内部 API | FastAPI 内置路由 | 题目允许自建 mock 服务，同进程最简 |
| 会话 | 内存 + SQLite 持久化（按用户+会话隔离） | 多轮对话上下文隔离是验收点 |
| 测试 | pytest ≥3 条（含 **Mock LLM**，不依赖真实 API） | 满足工程化底线 |

## 二、目录结构（遵守单文件≤500行）

```
xiaosu/
├── backend/                    # FastAPI 主服务（uv 管理）
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py             # 入口：API 路由 + 钉钉 stream 启动
│   │   ├── config.py           # 全部配置走环境变量（.env）
│   │   ├── schemas.py          # Pydantic 模型
│   │   ├── knowledge/          # 知识库：上传/解析/切块/索引
│   │   ├── agent/              # 问答核心：检索 + prompt + 工具调用
│   │   ├── tools/              # 工具：mock API 客户端 / 时间
│   │   ├── session/            # 多轮会话（按用户隔离）
│   │   ├── im/                 # 钉钉适配层（stream 收发 + 卡片回复）
│   │   └── mock_api/           # mock 内部服务（employees/attendance/orders）
│   ├── data/                   # 上传文档 + Chroma + SQLite（gitignore）
│   ├── logs/                   # 日志输出（gitignore）
│   └── tests/                  # pytest（含 mock_llm 测试）
├── web/                        # React 管理后台（pnpm）
│   └── src/pages/              # 文档管理 / 对话日志 / 设置 / 备用聊天
├── scripts/
│   ├── start.sh                # 一条命令启动前后端
│   ├── seed_data.sh            # 生成知识库文档 + mock 数据
│   └── test.sh                 # 跑测试
├── .env.example                # 配置模板（.env 绝不入库）
├── README.md                   # 架构图/安装/使用/技术栈/Roadmap
├── AI_USAGE.md                 # 15分核心：真实记录 AI 使用过程
├── 自评.md                     # ≤1页
└── PLAN.md                     # 本文档
```

## 三、核心流程

```
钉钉群 @小苏
   │  Stream 长连接（无需公网）
   ▼
钉钉适配层 → 识别用户/会话ID
   ▼
Agent 核心（openai function calling）
   ├─ 判断：检索知识库 或 调工具 或 直接答
   ├─ 检索：文档切块→Chroma→top-k→拼进 prompt（带出处）
   ├─ 工具：/api/employee/{id}、/api/attendance、/api/orders、当前时间
   ├─ 多轮：按 用户ID+会话 取历史
   └─ 流式/一次性返回 → 钉钉卡片回复（带引用链接）
   ▼
Web 后台：文档上传/列表/删除 + 对话日志（含工具调用与 Token）
```

## 四、里程碑（按评分权重排序）

| # | 里程碑 | 对应评分 | 说明 |
|---|--------|----------|------|
| M0 | 工程化底座 | 10 | uv+FastAPI 骨架、scripts、.env.example、日志 logs/、git init |
| M1 | 文档知识库 | 12 | 上传(MD/PDF/Word/TXT)/列表/删除/**增量更新同名替换** |
| M2 | 智能问答 | 18 | RAG+引用+流式+拒答+多轮 |
| M3 | 工具调用 | 12 | mock API 2个 + 时间工具，**模型自主决策**（function calling） |
| M4 | 钉钉集成 | 15 核心 | Stream 收发、多轮隔离、引用展示、错误兜底 |
| M5 | Web 管理后台 | 8 | 文档管理 + 对话日志 + 设置 + 备用聊天页 |
| M6 | 测试+文档+演示 | 22 | pytest≥3（Mock LLM）、README、**AI_USAGE.md**、自评.md、Demo 部署 |

> 关键路径：M0→M1→M2→M3→M4（验收必须 IM 里能跑）→M5→M6

## 五、你需要配合做的（3 件事，我逐步带你）

1. **钉钉机器人注册**（约 20 分钟）：开放平台 → 开发者后台 → 创建企业内部应用 → 启用机器人 → 拿 **AppKey/AppSecret**（Stream 模式不用配公网回调）。我给逐步指引。
2. **LLM API Key**：推荐 DeepSeek（便宜、OpenAI 兼容，`https://api.deepseek.com`）或通义/GLM，充值几块钱够测试。
3. **AI_USAGE.md 的真实素材**：15 分且"全是套话直接出局"——我按真实开发过程记录，但**需要你确认细节属实**，不能编。

## 六、风险与应对

| 风险 | 应对 |
|------|------|
| 钉钉 Stream 模式 SDK 兼容性 | 提前查官方文档；备选 Webhook+内网穿透（natapp） |
| API Key 泄漏入库 | .env 严格 gitignore + 提交前 `git log -p` 自检 |
| 面试现场改代码 | 代码拆分清晰、关键位置陪你把关 |
| 单文件≤500行/单目录≤8文件 | 按模块拆，写码时用工具检查 |
| 无真实 LLM 时无法联调 | Mock LLM 测试先行，保证验收脚本能跑 |

## 七、验收自测清单（面试前用题目 7.1-7.6 过一遍）

- [ ] 7.1 三条基础问答带引用命中
- [ ] 7.2 工具调用：员工部门/订单汇总/当前时间
- [ ] 7.3 多轮："他上周来上班几天"能理解指代
- [ ] 7.4 拒答：CEO 家庭住址 / 2030 销售目标
- [ ] 7.5 Key 改无效值 → IM 友好报错
- [ ] 7.6 后台能看到全部对话日志；上传新文档立刻可问；删除后不再命中
