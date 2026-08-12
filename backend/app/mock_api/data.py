"""Mock 内部数据：员工 / 考勤 / 销售订单（笔试模拟数据）"""

EMPLOYEES = {
    "001": {"name": "张伟", "department": "技术部", "position": "后端工程师", "hire_date": "2023-03-15"},
    "002": {"name": "李娜", "department": "市场部", "position": "市场专员", "hire_date": "2022-07-01"},
    "003": {"name": "王强", "department": "财务部", "position": "会计", "hire_date": "2021-11-20"},
    "004": {"name": "赵敏", "department": "销售部", "position": "销售经理", "hire_date": "2020-05-06"},
}

ATTENDANCE = {
    "001": {"employee_id": "001", "days": [{"date": "2026-08-07", "check_in": "08:55", "check_out": "18:02"},
                                           {"date": "2026-08-08", "check_in": "09:10", "check_out": "18:30"},
                                           {"date": "2026-08-11", "check_in": "08:50", "check_out": "17:58"}]},
    "002": {"employee_id": "002", "days": [{"date": "2026-08-07", "check_in": "09:20", "check_out": "18:40"},
                                           {"date": "2026-08-08", "check_in": "09:01", "check_out": "18:10"},
                                           {"date": "2026-08-11", "check_in": "08:45", "check_out": "18:15"}]},
    "003": {"employee_id": "003", "days": [{"date": "2026-08-07", "check_in": "08:58", "check_out": "18:00"},
                                           {"date": "2026-08-08", "check_in": "09:12", "check_out": "18:22"},
                                           {"date": "2026-08-11", "check_in": "08:52", "check_out": "18:05"}]},
    "004": {"employee_id": "004", "days": [{"date": "2026-08-07", "check_in": "09:05", "check_out": "19:20"},
                                           {"date": "2026-08-08", "check_in": "09:00", "check_out": "18:50"},
                                           {"date": "2026-08-11", "check_in": "08:55", "check_out": "18:30"}]},
}

ORDERS = {
    "004": {"employee_id": "004", "total_orders": 86, "total_amount": 1265000.0, "region": "华东区"},
    "001": {"employee_id": "001", "total_orders": 0, "total_amount": 0.0, "region": "-"},
}


def get_employee(employee_id: str) -> dict | None:
    return EMPLOYEES.get(employee_id)


def get_attendance(employee_id: str) -> dict | None:
    return ATTENDANCE.get(employee_id)


def get_orders(employee_id: str) -> dict | None:
    return ORDERS.get(employee_id)
