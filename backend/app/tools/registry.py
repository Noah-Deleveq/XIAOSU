"""工具注册表：OpenAI function calling 的 schema 与执行器

模型通过 tools 自主决定调用哪个工具，执行结果回传给模型生成最终答案。
（不写死 if-else 路由 —— 一切由模型决策）
"""
import datetime
import json

from app.mock_api import data

# ---- 工具 schema（给模型的描述） ----
TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_employee",
            "description": "查询员工信息：部门、职位、入职日期。入参为员工编号（如 001）",
            "parameters": {
                "type": "object",
                "properties": {"employee_id": {"type": "string", "description": "员工编号，如 001"}},
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_attendance",
            "description": "查询员工最近的考勤打卡记录",
            "parameters": {
                "type": "object",
                "properties": {"employee_id": {"type": "string", "description": "员工编号，如 001"}},
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_orders",
            "description": "查询员工的销售订单汇总（订单数、金额、区域）",
            "parameters": {
                "type": "object",
                "properties": {"employee_id": {"type": "string", "description": "员工编号，如 004"}},
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "current_time",
            "description": "获取当前日期和时间",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def execute_tool(name: str, arguments: str) -> str:
    """执行工具调用，返回 JSON 字符串（回传给模型）"""
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        args = {}
    try:
        if name == "current_time":
            result = {"now": datetime.datetime.now().isoformat()}
        elif name == "query_employee":
            result = data.get_employee(args.get("employee_id", "")) or {"error": "员工不存在"}
        elif name == "query_attendance":
            result = data.get_attendance(args.get("employee_id", "")) or {"error": "员工不存在"}
        elif name == "query_orders":
            result = data.get_orders(args.get("employee_id", "")) or {"error": "员工不存在"}
        else:
            result = {"error": f"未知工具: {name}"}
    except Exception as e:  # noqa: BLE001
        result = {"error": str(e)}
    return json.dumps(result, ensure_ascii=False)
