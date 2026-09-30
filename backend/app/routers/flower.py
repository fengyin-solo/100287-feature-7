"""花卉造景接口：维护花卉造景，覆盖开始造景、记录盛花、安排换花等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, FlowerPageResult
from app.services.flower import FlowerService

router = APIRouter(prefix="/api/flower", tags=["花卉造景"])

service = FlowerService()

LIST_FIELDS = ["造景编号", "造景主题", "花卉品种", "景观面积", "花期起止", "换花周期", "养护人员", "造景状态", "所在区域", "花期阶段"]
STATUSES = ["造景中", "盛花期", "凋谢期", "已换花"]


@router.get("", response_model=FlowerPageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按造景编号、主题、品种或区域检索"),
    area: str | None = Query(default=None, description="所在区域"),
    stage: str | None = Query(default=None, description="花期阶段：造景中、盛花期、凋谢期、已换花"),
    page: int = 1,
    size: int = 20,
) -> FlowerPageResult[dict]:
    """按区域与花期阶段过滤，并始终按换花优先级从紧到松返回。"""
    if page < 1:
        raise HTTPException(status_code=400, detail="页码不能小于 1")
    if size < 1 or size > 200:
        raise HTTPException(status_code=400, detail="每页范围为 1 至 200 条，请调整分页参数")
    items, total, quality = service.list_entries(
        keyword=keyword,
        area=area,
        stage=stage,
        page=page,
        size=size,
    )
    return FlowerPageResult(
        items=items,
        total=total,
        page=page,
        size=size,
        registered_total=quality["registered_total"],
        available_total=quality["available_total"],
        quality=quality,
    )


@router.get("/options")
def list_options() -> dict[str, list[str]]:
    """提供区域与花期阶段下拉选项，保证列表页和其他页面取同一套口径。"""
    return service.list_options()


@router.get("/export")
def export_entries(
    keyword: str | None = None,
    area: str | None = None,
    stage: str | None = None,
) -> dict[str, Any]:
    """导出当前筛选条件下、去重和缺字段过滤后的全量数据。"""
    items, total, quality = service.list_entries(
        keyword=keyword,
        area=area,
        stage=stage,
        page=1,
        size=10000,
    )
    return {"module": "flower", "total": total, "quality": quality, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条花卉造景明细；不存在或已被新版本替代时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"花卉造景 {entry_id} 不存在、已归档或已被新版本替代")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条花卉造景，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="花卉造景已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条花卉造景执行开始造景、记录盛花、安排换花；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
