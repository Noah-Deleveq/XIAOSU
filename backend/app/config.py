"""全局配置：全部来自环境变量（.env），不硬编码任何密钥"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 运行环境
    app_env: str = "dev"

    # LLM（OpenAI 兼容接口）
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    # 钉钉（Stream 模式机器人）
    dingtalk_app_key: str = ""
    dingtalk_app_secret: str = ""

    # 数据与日志目录
    data_dir: str = "data"
    log_dir: str = "logs"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
