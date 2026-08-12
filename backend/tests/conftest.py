"""测试前统一清理 data（仅一次，避免测试间互相破坏）"""
import shutil

shutil.rmtree("data", ignore_errors=True)
