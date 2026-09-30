"""花卉造景接口：按区域/花期阶段筛选、按换花周期从紧到松排序，并维护换花规矩。

列表返回的不只是本页数据，还带一份对账信息（登记总数、重复合并、缺字段过滤、
在册片数、筛选片数、本页片数），让“筛出来的片数和总数对不上”一眼能看出原因。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas import ActionResult, EntryPayload
from app.services.flower import PHASES
from app.services.flower import FlowerService

router = APIRouter(prefix="/api/flower", tags=["花卉造景"])

service = FlowerService()

LIST_FIELDS = [
    "造景编号", "造景主题", "所在区域", "花卉品种", "景观面积",
    "花期起", "花期止", "花期阶段", "换花周期天数", "下次换花日",
    "剩余天数", "换花优先级", "养护人员", "造景状态",
]


class RulesPayload(BaseModel):
    """调整换花规矩：每个花期阶段对应的换花周期天数。"""

    cycles: dict[str, int] = Field(default_factory=dict)


def _validate_page(size: int) -> None:
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")


@router.get("")
def list_entries(
    keyword: str | None = Query(default=None, description="按造景编号/主题/品种检索"),
    region: str | None = Query(default=None, description="所在区域，精确匹配"),
    phase: str | None = Query(default=None, description=f"花期阶段：{'、'.join(PHASES)}"),
    priority: str | None = Query(default=None, description="换花优先级：已逾期/紧急/偏紧/正常/宽松"),
    page: int = 1,
    size: int = 20,
) -> dict:
    """按区域与花期阶段定位造景，并按换花周期从紧到松排列。"""
    _validate_page(size)
    if phase and phase not in PHASES:
        raise HTTPException(status_code=400, detail=f"花期阶段「{phase}」不合法，可选：{'、'.join(PHASES)}")
    items, total, summary = service.list_entries(
        keyword=keyword, region=region, phase=phase,
        priority=priority, page=page, size=size,
    )
    return {"items": items, "total": total, "page": page, "size": size, "summary": summary}


@router.get("/meta")
def meta() -> dict:
    """筛选项与当前换花规矩：下拉项从在册数据汇总，不写死在前端。"""
    return service.meta()


@router.get("/rules")
def get_rules() -> dict:
    """读取当前换花规矩（每阶段周期天数、阶段区间、最近更新时间）。"""
    return service.get_rules()


@router.put("/rules")
def update_rules(payload: RulesPayload) -> dict:
    """换一套周期规矩：校验通过后按新规矩重算全部在册造景的优先级与排序。"""
    if not payload.cycles:
        raise HTTPException(status_code=400, detail="请至少提交一个花期阶段的周期天数")
    try:
        return service.update_rules(payload.cycles)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/export/all")
def export_entries(
    region: str | None = None,
    phase: str | None = None,
) -> dict:
    """导出当前筛选口径下的全量造景（同样经过去重、缺字段过滤与优先级重算）。"""
    items, total, summary = service.list_entries(region=region, phase=phase, page=1, size=10000)
    return {"module": "flower", "total": total, "summary": summary, "items": items}


@router.get("/{entry_id}")
def get_entry(entry_id: int) -> dict:
    """读取单条花卉造景明细；不存在或已被过滤/合并时给出可读说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"花卉造景 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条花卉造景；编号重复时不会覆盖，读数时自动只留最新一版。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="花卉造景已登记，列表已按最新版本去重", entry=entry)


class ActionPayload(BaseModel):
    """动作提交：兼容 {action} 与 {values: {action}} 两种包法。"""

    action: str | None = None
    values: dict[str, str] = Field(default_factory=dict)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    """安排换花：重置上次换花日并按当前规矩重新计算优先级。"""
    action = str(payload.action or payload.values.get("action") or "").strip()
    if action != "安排换花":
        return ActionResult(ok=False, message=f"动作「{action}」不属于花卉造景可执行范围")
    entry, message = service.mark_changed(entry_id)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export/all")
def export_entries(
    region: str | None = None,
    phase: str | None = None,
) -> dict:
    """导出当前筛选口径下的全量造景（同样经过去重、缺字段过滤与优先级重算）。"""
    items, total, summary = service.list_entries(region=region, phase=phase, page=1, size=10000)
    return {"module": "flower", "total": total, "summary": summary, "items": items}
