"""钉钉 / 企业微信共用的消息处理工具。"""
import re


def clean_mention(text: str) -> str:
    """去掉消息开头的 @机器人 及空白，取出真正的问题。"""
    cleaned = re.sub(r"@[\w\u4e00-\u9fa5]+\s*", "", text, count=1)
    return cleaned.strip()


def build_reply(result: dict) -> str:
    """组装回复文本：答案 + 引用来源。"""
    reply = result["answer"]
    refs = [r["name"] for r in result["references"]]
    if refs:
        sources = "、".join(dict.fromkeys(refs))
        reply += f"\n\n📎 来源：{sources}"
    return reply
