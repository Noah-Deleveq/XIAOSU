"""Token 成本估算（按公开单价，元 / 百万 tokens，演示用可调）"""
# 模型 -> (输入单价, 输出单价)
PRICES: dict[str, tuple[float, float]] = {
    "deepseek-chat": (2.0, 8.0),
    "deepseek-v4-flash": (0.27, 1.1),
    "glm-4-flash": (0.1, 0.1),
    "qwen-plus": (0.8, 2.0),
    "qwen-turbo": (0.3, 0.6),
}
DEFAULT_PRICE: tuple[float, float] = (1.0, 2.0)


def estimate_cost(model: str, usage: dict, prices: dict[str, tuple[float, float]] | None = None) -> float:
    """估算一次对话成本（元）。usage: {prompt_tokens, completion_tokens}"""
    table = prices or PRICES
    in_price, out_price = table.get(model, DEFAULT_PRICE)
    prompt = usage.get("prompt_tokens", 0) or 0
    completion = usage.get("completion_tokens", 0) or 0
    return round((prompt * in_price + completion * out_price) / 1_000_000, 6)
