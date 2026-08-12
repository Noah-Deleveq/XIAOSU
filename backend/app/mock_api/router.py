"""Mock 内部服务 HTTP 接口（笔试验收用，可 curl 验证）"""
from fastapi import APIRouter, HTTPException

from app.mock_api import data

router = APIRouter(prefix="/api", tags=["mock-api"])


@router.get("/employee/{employee_id}")
def employee(employee_id: str) -> dict:
    d = data.get_employee(employee_id)
    if d is None:
        raise HTTPException(404, "员工不存在")
    return d


@router.get("/attendance/{employee_id}")
def attendance(employee_id: str) -> dict:
    d = data.get_attendance(employee_id)
    if d is None:
        raise HTTPException(404, "员工不存在")
    return d


@router.get("/orders/{employee_id}")
def orders(employee_id: str) -> dict:
    d = data.get_orders(employee_id)
    if d is None:
        raise HTTPException(404, "员工不存在")
    return d
