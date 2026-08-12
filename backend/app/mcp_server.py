"""MCP Server：把「小苏」的知识库问答 / 工具调用暴露为 MCP，可被 Claude Desktop / Cursor 调用

运行：uv run python -m app.mcp_server（stdio 模式）
Claude Desktop 配置示例见 README「加分项」章节。
"""
import datetime
import json

from app.agent.qa import QaEngine
from app.state import index, sessions
from app.tools.registry import execute_tool

try:
    from fastmcp import FastMCP
except ImportError:  # 依赖未装时导入不炸（测试可跳过）
    FastMCP = None

_engine = QaEngine(index, sessions)


def _make_mcp():
    if FastMCP is None:
        raise RuntimeError("请先安装 fastmcp：uv add fastmcp")
    mcp = FastMCP("小苏知识库")

    @mcp.tool()
    def search_knowledge(query: str, k: int = 4) -> str:
        """在公司知识库中检索与问题相关的文档片段，返回带来源的片段列表"""
        hits = index.search(query, k=k)
        if not hits:
            return json.dumps({"hits": []}, ensure_ascii=False)
        return json.dumps(
            {
                "hits": [
                    {"name": h["name"], "chunk_index": h["chunk_index"], "text": h["text"][:300]}
                    for h in hits
                ]
            },
            ensure_ascii=False,
        )

    @mcp.tool()
    def ask_xiaosu(question: str) -> str:
        """向公司内部 AI 助手「小苏」提问，返回带引用的回答（自动检索知识库 / 调用工具 / 拒答）"""
        result = _engine.answer("mcp", "mcp", question)
        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    def query_employee(employee_id: str) -> str:
        """查询员工信息：部门、职位、入职日期"""
        return execute_tool("query_employee", json.dumps({"employee_id": employee_id}))

    @mcp.tool()
    def query_attendance(employee_id: str) -> str:
        """查询员工最近的考勤打卡记录"""
        return execute_tool("query_attendance", json.dumps({"employee_id": employee_id}))

    @mcp.tool()
    def query_orders(employee_id: str) -> str:
        """查询员工的销售订单汇总（订单数、金额、区域）"""
        return execute_tool("query_orders", json.dumps({"employee_id": employee_id}))

    @mcp.tool()
    def current_time() -> str:
        """获取当前日期和时间"""
        return datetime.datetime.now().isoformat()

    return mcp


mcp = _make_mcp()


def main() -> None:
    mcp.run()  # stdio 模式


if __name__ == "__main__":
    main()
