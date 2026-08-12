# 开源与参考声明

## 应用代码

本仓库中的应用层代码（`backend/app/`、`web/src/`、`scripts/`）为项目原创实现，不包含大段未署名的开源项目代码。少量 API 调用写法参考了官方 SDK 文档，并在下方列出出处。

## 主要开源依赖

| 依赖 | 用途 | 官方地址 |
|---|---|---|
| FastAPI | Python Web 框架 | https://fastapi.tiangolo.com |
| Pydantic | 配置与请求强类型 | https://docs.pydantic.dev |
| OpenAI Python SDK | LLM 兼容接口与 function calling | https://github.com/openai/openai-python |
| jieba | 中文分词与 BM25 检索 | https://github.com/fxsjy/jieba |
| pypdf | PDF 文本解析 | https://github.com/py-pdf/pypdf |
| python-docx | Word 文档解析 | https://github.com/python-openxml/python-docx |
| dingtalk-stream | 钉钉 Stream 长连接 | https://github.com/open-dingtalk/dingtalk-stream-sdk-python |
| lark-oapi | 飞书开放平台 SDK | https://github.com/larksuite/oapi-sdk-python |
| React | 前端 UI | https://react.dev |
| Vite | 前端构建 | https://vite.dev |
| Tailwind CSS | 样式 | https://tailwindcss.com |
| fastmcp | MCP Server | https://github.com/jlowin/fastmcp |

## 官方接口参考

- 钉钉机器人 Stream 模式：https://open.dingtalk.com/document/orgapp/stream-mode
- 飞书机器人长连接：https://open.feishu.cn/document/server-docs/im-v1/message-receive-event/event-subscription-configure
- 飞书交互卡片：https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/feishu-card-cardkit/feishu-cardkit-overview
- 企业微信自建应用消息：https://developer.work.weixin.qq.com/document/path/90236
- OpenAI 兼容接口与工具调用：https://platform.openai.com/docs/guides/function-calling

如果评审时发现某段代码与公开实现相似，通常来自上述官方文档或 SDK 的标准调用方式；本项目的业务逻辑、知识库索引、问答编排和 IM 消息处理均为独立实现。
