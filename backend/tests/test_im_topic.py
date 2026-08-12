"""机器人 topic 注册验证（回归：曾注册 'chatbot' 字符串导致消息全被丢弃）"""
import dingtalk_stream

from app.im.dingtalk_bot import build_stream_client


def test_stream_client_registers_correct_topic():
    """注册的 topic 必须是钉钉 chatbot 消息的 TOPIC"""
    client = build_stream_client()
    assert list(client.callback_handler_map.keys()) == [
        dingtalk_stream.ChatbotMessage.TOPIC
    ]
