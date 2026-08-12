"""Pydantic 数据模型（强类型）"""
from pydantic import BaseModel


class DocUploadOut(BaseModel):
    """文档上传结果"""

    id: str
    name: str
    status: str


class ChatRequest(BaseModel):
    """通用对话请求（Web 备用聊天页用）"""

    user_id: str
    session_id: str
    message: str
