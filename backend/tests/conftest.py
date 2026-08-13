"""测试前统一清理 data，并固定 IM 开关，避免本地 .env 影响测试结果"""
import shutil

shutil.rmtree("data", ignore_errors=True)

from app import state  # noqa: E402

state.im_enabled["dingtalk"] = True
state.im_enabled["feishu"] = True
