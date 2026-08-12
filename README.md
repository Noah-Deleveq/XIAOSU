
## 钉钉集成（M4）

- 技术：钉钉官方 **Stream 模式**（长连接 SDK），无需公网 IP/域名
- 配置：backend/.env 里 DINGTALK_APP_KEY / DINGTALK_APP_SECRET
- 启动：双击 scripts/start.bat，或 （自动连接钉钉）
- 使用：钉钉里 **@小苏** 提问即可（单聊/群聊都行）
- 消息流：@小苏 → 去 @ → RAG/工具 → 回复（含引用来源）
- 回复走 session_webhook（官方 reply_text），无需额外权限配置
