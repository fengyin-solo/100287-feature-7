"""花卉造景业务规则：去重、缺字段过滤、花期阶段判定与换花优先级都收在这里。

口径说明（列表、详情、导出、概览共用同一条管线，保证各处看到的是同一份结果）：
1. 同一造景编号重复登记时，只保留「登记时间」最新的一版，旧版计入合并明细；
2. 景观面积或花卉品种缺失的记录先过滤掉，并在过滤明细里逐条说明原因；
3. 按「花期起止」与当前日期判定花期阶段，再用当前换花规矩（每阶段周期天数）
   推算下次换花日、剩余天数与换花优先级；
4. 换花规矩调整后，下次查询即按新规矩对全部在册造景重算一遍优先级。
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Any

from app.store import store

MODULE = "flower"

# 登记时必填（缺失则不允许入库）；另外两个字段「景观面积、花卉品种」缺失时
# 不在入库时拒绝，而是在读数管线里过滤并汇报，满足“先过滤掉并说清是哪几条”。
REQUIRED_FIELDS = ["造景编号", "造景主题", "所在区域"]

# 花期阶段：从花期起止里按区间占比切分；已过花期的归入凋谢期。
PHASES = ["蕾花期", "初花期", "盛花期", "末花期", "凋谢期"]
# 阶段在花期区间内的占比切点，例如盛花期约占整个花期的中段 45%。
PHASE_CUTOFFS = {
    "蕾花期": (0.0, 0.15),
    "初花期": (0.15, 0.35),
    "盛花期": (0.35, 0.80),
    "末花期": (0.80, 1.0),
}

# 默认换花规矩：每个花期阶段允许摆放的周期天数（越接近凋谢，周期越紧）。
DEFAULT_RULES: dict[str, Any] = {
    "周期天数": {"蕾花期": 30, "初花期": 21, "盛花期": 14, "末花期": 7, "凋谢期": 3},
    "阶段区间": deepcopy(PHASE_CUTOFFS),
    "更新时间": None,
}

# 优先级标签按“剩余天数”分档（从紧到松）。
PRIORITY_TIERS = [
    ("已逾期", -10**9, 0),
    ("紧急", 1, 3),
    ("偏紧", 4, 7),
    ("正常", 8, 14),
    ("宽松", 15, 10**9),
]

# 阶段到台账状态的映射，供看板 pending/abnormal 统计沿用。
PHASE_STATUS = {
    "蕾花期": "造景中",
    "初花期": "造景中",
    "盛花期": "盛花期",
    "末花期": "凋谢期",
    "凋谢期": "凋谢期",
}


def _today() -> date:
    return date.today()


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_registered_at(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.min
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.min


def priority_tier(remaining_days: int) -> str:
    for label, lower, upper in PRIORITY_TIERS:
        if lower <= remaining_days <= upper:
            return label
    return "宽松"


class FlowerService:
    def __init__(self) -> None:
        self._rules: dict[str, Any] = deepcopy(DEFAULT_RULES)

    # ----- 换花规矩 -----------------------------------------------------
    def get_rules(self) -> dict[str, Any]:
        return deepcopy(self._rules)

    def update_rules(self, cycles: dict[str, int]) -> dict[str, Any]:
        """换一套新的周期规矩：校验后落库，并按新规矩重算全部在册造景。"""
        bad = [phase for phase in cycles if phase not in PHASES]
        if bad:
            raise ValueError(f"未知花期阶段：{'、'.join(bad)}")
        invalid = [phase for phase, days in cycles.items() if not isinstance(days, int) or days <= 0 or days > 365]
        if invalid:
            raise ValueError(f"周期天数需为 1~365 的整数：{'、'.join(invalid)}")
        # 先按旧规矩记一份排序，再落新规矩，重算结果才能体现“变了哪几条”。
        before = [(item["造景编号"], item["换花优先级"], item["剩余天数"])
                  for item in self._pipeline()[0]]
        self._rules["周期天数"].update(cycles)
        self._rules["更新时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        after_rows = self._pipeline()[0]
        after = {item["造景编号"]: (item["换花优先级"], item["剩余天数"]) for item in after_rows}
        moved: list[dict[str, Any]] = []
        for code, old_tier, old_days in before:
            new_tier, new_days = after[code]
            if (old_tier, old_days) != (new_tier, new_days):
                moved.append({
                    "造景编号": code,
                    "旧优先级": old_tier,
                    "新优先级": new_tier,
                    "旧剩余天数": old_days,
                    "新剩余天数": new_days,
                })
        recomputed = {
            "在册片数": len(after_rows),
            "优先级变动片数": len(moved),
            "变动明细": moved,
            "最新排序": [item["造景编号"] for item in after_rows],
        }
        return {"rules": deepcopy(self._rules), "recomputed": recomputed}

    # ----- 读数管线（所有查询共用） -------------------------------------
    def _pipeline(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        rows = store.rows(MODULE)
        total_registered = len(rows)

        # 1) 去重：同一造景编号只留登记时间最新的一版。
        latest: dict[str, dict[str, Any]] = {}
        merged_duplicates: list[dict[str, Any]] = []
        for row in rows:
            code = str(row.get("造景编号") or "").strip()
            current = latest.get(code)
            if current is None:
                latest[code] = row
                continue
            if _parse_registered_at(row.get("登记时间")) >= _parse_registered_at(current.get("登记时间")):
                winner, loser = row, current
            else:
                winner, loser = current, row
            latest[code] = winner
            merged_duplicates.append({
                "造景编号": code,
                "保留版本": f"{winner.get('登记时间') or '未登记时间'}（id={winner.get('id')}）",
                "合并版本": f"{loser.get('登记时间') or '未登记时间'}（id={loser.get('id')}）",
            })

        # 2) 缺字段过滤：景观面积或花卉品种缺失（含空串与非数字面积）先挡掉。
        active: list[dict[str, Any]] = []
        filtered_out: list[dict[str, Any]] = []
        for row in latest.values():
            missing: list[str] = []
            if not str(row.get("花卉品种") or "").strip():
                missing.append("花卉品种")
            area_text = str(row.get("景观面积") or "").strip()
            area_value: float | None = None
            try:
                area_value = float(area_text)
            except (TypeError, ValueError):
                pass
            if not area_text or area_value is None or area_value <= 0:
                missing.append("景观面积")
            if missing:
                filtered_out.append({
                    "id": row.get("id"),
                    "造景编号": row.get("造景编号"),
                    "造景主题": row.get("造景主题"),
                    "原因": f"缺少有效{'、'.join(missing)}",
                    "登记时间": row.get("登记时间"),
                })
                continue
            enriched = self._enrich(row, area_value)
            active.append(enriched)

        # 3) 从紧到松：剩余天数升序，逾期在最前；再按面积大、编号小兜底。
        active.sort(key=lambda item: (
            item["剩余天数"],
            -float(item["景观面积"]),
            str(item["造景编号"]),
        ))

        reconciliation = {
            "登记总条数": total_registered,
            "重复合并条数": len(merged_duplicates),
            "缺字段过滤条数": len(filtered_out),
            "在册片数": len(active),
            "重复合并明细": merged_duplicates,
            "缺字段过滤明细": filtered_out,
            "规矩更新时间": self._rules.get("更新时间"),
        }
        return active, reconciliation

    def _enrich(self, row: dict[str, Any], area_value: float) -> dict[str, Any]:
        today = _today()
        start = _parse_date(row.get("花期起"))
        end = _parse_date(row.get("花期止"))
        if start and end and end >= start:
            if today < start:
                phase = "蕾花期"
            elif today > end:
                phase = "凋谢期"
            else:
                ratio = (today - start).days / max((end - start).days, 1)
                phase = next(
                    name for name, (lower, upper) in self._rules["阶段区间"].items()
                    if lower <= ratio < upper or (name == "末花期" and ratio == 1.0)
                )
        else:
            phase = "凋谢期"

        cycles: dict[str, int] = self._rules["周期天数"]
        cycle_days = cycles.get(phase, cycles["凋谢期"])
        last_change = _parse_date(row.get("上次换花日")) or start or today
        next_change = date.fromordinal(last_change.toordinal() + cycle_days)
        remaining_days = next_change.toordinal() - today.toordinal()

        item = dict(row)
        item["景观面积"] = area_value
        item["花期阶段"] = phase
        item["换花周期天数"] = cycle_days
        item["下次换花日"] = next_change.isoformat()
        item["剩余天数"] = remaining_days
        item["换花优先级"] = priority_tier(remaining_days)
        item["造景状态"] = PHASE_STATUS.get(phase, row.get("造景状态") or "造景中")
        item["status"] = item["造景状态"]
        item["pending"] = phase != "盛花期"
        item["abnormal"] = remaining_days <= 0
        return item

    # ----- 对外查询 -----------------------------------------------------
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        region: str | None = None,
        phase: str | None = None,
        priority: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
        active, reconciliation = self._pipeline()

        region = (region or "").strip()
        phase = (phase or "").strip()
        priority = (priority or "").strip()
        keyword = (keyword or "").strip()

        matched = active
        if region:
            matched = [row for row in matched if str(row.get("所在区域") or "").strip() == region]
        if phase:
            matched = [row for row in matched if row.get("花期阶段") == phase]
        if priority:
            matched = [row for row in matched if row.get("换花优先级") == priority]
        if keyword:
            matched = [
                row for row in matched
                if keyword in str(row.get("造景编号") or "")
                or keyword in str(row.get("造景主题") or "")
                or keyword in str(row.get("花卉品种") or "")
            ]

        total = len(matched)
        page = max(page, 1)
        start = (page - 1) * size
        page_items = matched[start:start + size]

        summary = dict(reconciliation)
        summary.update({
            "筛选片数": total,
            "本页片数": len(page_items),
            "筛选条件": {"区域": region or None, "花期阶段": phase or None,
                      "换花优先级": priority or None, "关键词": keyword or None},
        })
        return page_items, total, summary

    def meta(self) -> dict[str, Any]:
        """筛选下拉项：区域、花期阶段、优先级都来自在册数据，避免写死。"""
        active, reconciliation = self._pipeline()
        return {
            "regions": sorted({str(row.get("所在区域") or "").strip() for row in active if row.get("所在区域")}),
            "phases": PHASES,
            "priorities": [label for label, _, _ in PRIORITY_TIERS],
            "rules": self.get_rules(),
            "reconciliation": reconciliation,
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        active, _ = self._pipeline()
        for row in active:
            if int(row.get("id", 0)) == entry_id:
                return row
        # 被去重或过滤掉的记录也要能解释清楚去向。
        for raw in store.rows(MODULE):
            if int(raw.get("id", 0)) == entry_id:
                return {**raw, "已归档": True}
        return None

    # ----- 写入 ---------------------------------------------------------
    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in ["造景编号", "造景主题", "所在区域", "花卉品种", "景观面积",
                      "花期起", "花期止", "上次换花日", "养护人员"]:
            entry[field] = values.get(field)
        entry["登记时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry["造景状态"] = "造景中"
        entry["status"] = "造景中"
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def mark_changed(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        """安排换花：把上次换花日重置为今天，下次查询自然按规矩重新排优先级。"""
        raw = store.find(MODULE, entry_id)
        if raw is None:
            return None, f"花卉造景 {entry_id} 不存在或已归档"
        raw["上次换花日"] = _today().isoformat()
        entry = self.get_entry(entry_id)
        return entry, "花卉造景已安排换花，换花优先级已重算"
