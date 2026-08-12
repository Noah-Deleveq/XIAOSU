"""钉钉消息处理测试：@去重、回复组装"""
from app.im.dingtalk_bot import build_reply, clean_mention


def test_clean_mention():
    """去掉开头的 @小苏"""
    assert clean_mention("@小苏 员工每年几天年假？") == "员工每年几天年假？"
    assert clean_mention("@小苏\n报销需要什么？") == "报销需要什么？"
    # 无 @ 时原样返回
    assert clean_mention("直接问问题") == "直接问问题"


def test_build_reply_with_references():
    """答案带引用来源"""
    result = {
        "answer": "员工每年 10 天带薪年假 [1]。",
        "references": [
            {"name": "员工手册.md", "text": "..."},
            {"name": "员工手册.md", "text": "..."},
            {"name": "FAQ.md", "text": "..."},
        ],
    }
    reply = build_reply(result)
    assert "10 天带薪年假" in reply
    assert "员工手册.md、FAQ.md" in reply  # 去重后
    assert "📎 来源" in reply


def test_build_reply_without_references():
    """无引用（如工具查询结果）时不加来源"""
    result = {"answer": "张伟在技术部。", "references": []}
    reply = build_reply(result)
    assert reply == "张伟在技术部。"
