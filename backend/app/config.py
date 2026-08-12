"""全局配置：全部来自环境变量（.env），不硬编码任何密钥"""
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class ProviderConfig(BaseModel):
    """一个 LLM 供应商（OpenAI 兼容接口）"""

    api_key: str = ""
    base_url: str = ""
    model: str = ""


class Settings(BaseSettings):
    # 运行环境
    app_env: str = "dev"

    # 当前激活的 LLM 供应商：deepseek / zhipu / dashscope
    llm_provider: str = "deepseek"

    # 多供应商配置（OpenAI 兼容 API；.env 中对应 DEEPSEEK_API_KEY / ZHIPU_API_KEY / DASHSCOPE_API_KEY）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    zhipu_api_key: str = ""
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_model: str = "glm-4-flash"

    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_model: str = "qwen-plus"

    # 旧版单供应商配置（兼容：供应商未填 api_key/model 时回退）
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    # LLM 调用容错：超时时间与失败重试次数
    llm_timeout_seconds: float = 60
    llm_max_retries: int = 2

    # 钉钉（Stream 模式机器人）
    dingtalk_app_key: str = ""
    dingtalk_app_secret: str = ""

    # 飞书（WebSocket 长连接）
    feishu_app_id: str = ""
    feishu_app_secret: str = ""

    # 数据与日志目录
    data_dir: str = "data"
    log_dir: str = "logs"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def deepseek(self) -> ProviderConfig:
        return ProviderConfig(
            api_key=self.deepseek_api_key,
            base_url=self.deepseek_base_url,
            model=self.deepseek_model,
        )

    @property
    def zhipu(self) -> ProviderConfig:
        return ProviderConfig(
            api_key=self.zhipu_api_key,
            base_url=self.zhipu_base_url,
            model=self.zhipu_model,
        )

    @property
    def dashscope(self) -> ProviderConfig:
        return ProviderConfig(
            api_key=self.dashscope_api_key,
            base_url=self.dashscope_base_url,
            model=self.dashscope_model,
        )

    def provider_names(self) -> list[str]:
        return ["deepseek", "zhipu", "dashscope"]

    def get_provider(self, name: str) -> ProviderConfig:
        """取某供应商配置；未单独配置时回退到旧版 LLM_* 变量，保证老 .env 仍可用"""
        p = getattr(self, name, None)
        if not isinstance(p, ProviderConfig):
            p = ProviderConfig()
        return ProviderConfig(
            api_key=p.api_key or self.llm_api_key,
            base_url=p.base_url or self.llm_base_url,
            model=p.model or self.llm_model,
        )


settings = Settings()
