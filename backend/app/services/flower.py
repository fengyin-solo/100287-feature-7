"""花卉造景业务规则：去重、字段校验、筛选口径与换花优先级都收在这里。"""
from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

from app.store import store

MODULE = "flower"
REQUIRED_FIELDS = ["造景编号", "造景主题", "花卉品种"]
DETAIL_FIELDS = [
    "造景编号",
    "造景主题",
    "花卉品种",
    "景观面积",
    "花期起止",
    "换花周期",
    "养护人员",
    "造景状态",
    "所在区域",
    "花期阶段",
]
STATUS_ORDER = ["造景中", "盛花期", "凋谢期", "已换花"]
ACTION_RULES = {"开始造景": "造景中", "记录盛花": "盛花期", "安排换花": "已换花"}
NEGATIVE_ACTIONS: list[str] = []

# 优先级标签在周期基础上再按花期阶段加权；凋谢期最紧，已完成换花的排到最后。
STAGE_URGENCY = {
    "凋谢期": 0,
    "盛花期": 2,
    "造景中": 7,
    "已换花": 30,
}
URGENCY_LABELS = [
    (10, "紧急"),
    (20, "较紧"),
    (45, "常规"),
    (math.inf, "宽松"),
]
UNIT_DAYS = {
    "日": 1,
    "天": 1,
    "周": 7,
    "月": 30,
    "季": 90,
    "年": 365,
}


class FlowerService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        area: str | None = None,
        stage: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
        catalog = self._catalog()
        rows = catalog["valid_rows"]

        if keyword:
            key = keyword.strip()
            rows = [
                row
                for row in rows
                if key
                in " ".join(
                    str(row.get(field, ""))
                    for field in ("造景编号", "造景主题", "花卉品种", "所在区域")
                )
            ]
        if area:
            rows = [row for row in rows if row.get("所在区域") == area]
        if stage:
            rows = [row for row in rows if row.get("花期阶段") == stage]

        rows = sorted(rows, key=self._priority_sort_key)
        total = len(rows)
        page = max(page, 1)
        start = (page - 1) * size
        return rows[start:start + size], total, catalog["quality"]

    def list_options(self) -> dict[str, list[str]]:
        catalog = self._catalog()
        areas = sorted({str(row.get("所在区域", "")).strip() for row in catalog["valid_rows"] if row.get("所在区域")})
        stages = [
            stage for stage in STATUS_ORDER
            if any(row.get("花期阶段") == stage for row in catalog["valid_rows"])
        ]
        return {"areas": areas, "stages": stages}

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        catalog = self._catalog()
        for row in catalog["valid_rows"]:
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not self._text(values.get(field))]
        if missing:
            return None, missing

        rows = store.rows(MODULE)
        code = self._text(values.get("造景编号"))
        # 同编号视为同一片造景的重复登记，只保留最新提交的这一版。
        rows[:] = [row for row in rows if self._text(row.get("造景编号")) != code]

        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in DETAIL_FIELDS:
            if field in values:
                entry[field] = values[field]
        entry["status"] = STATUS_ORDER[0]
        entry["造景状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self.get_entry(int(entry["id"])) or entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        catalog = self._catalog()
        entry = catalog["latest"].get(entry_id)
        if entry is None or not any(int(row.get("id", 0)) == entry_id for row in catalog["valid_rows"]):
            return None, f"花卉造景 {entry_id} 不存在、已归档或已被新版本替代"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于花卉造景可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["花期阶段"] = target
        entry["造景状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return self.get_entry(entry_id), f"花卉造景已{action}"

    def _catalog(self) -> dict[str, Any]:
        """每次按最新规则实时生成有效清单，避免规则调整后优先级沿用旧值。"""
        raw_rows = store.rows(MODULE)
        grouped: dict[str, list[dict[str, Any]]] = {}
        ungrouped: list[dict[str, Any]] = []
        for index, row in enumerate(raw_rows):
            code = self._text(row.get("造景编号"))
            if code:
                grouped.setdefault(code, []).append((index, row))
            else:
                ungrouped.append((index, row))

        deduped: list[dict[str, Any]] = []
        duplicates: list[dict[str, Any]] = []
        for code, versions in grouped.items():
            latest_index, latest = max(versions, key=lambda item: (int(item[1].get("id", 0)), item[0]))
            deduped.append(latest)
            for index, row in versions:
                if index == latest_index and row is latest:
                    continue
                duplicates.append(self._quality_item(
                    row,
                    f"造景编号 {code} 重复登记，已保留 id={latest.get('id')} 的最新版本",
                ))
        deduped.extend(row for _, row in ungrouped)
        deduped.sort(key=lambda row: int(row.get("id", 0)))

        valid_rows: list[dict[str, Any]] = []
        invalid_rows: list[dict[str, Any]] = []
        for row in deduped:
            missing = []
            if not self._text(row.get("花卉品种")):
                missing.append("花卉品种")
            if not self._text(row.get("景观面积")):
                missing.append("景观面积")
            if missing:
                invalid_rows.append(self._quality_item(row, f"缺少{'、'.join(missing)}"))
            else:
                valid_rows.append(self._decorate(row))

        latest_by_id = {
            int(row.get("id", 0)): row
            for row in deduped
        }

        stage_counts = {stage: 0 for stage in STATUS_ORDER}
        for row in valid_rows:
            stage = str(row.get("花期阶段") or "")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1

        quality = {
            "registered_total": len(raw_rows),
            "available_total": len(valid_rows),
            "duplicate_total": len(duplicates),
            "invalid_total": len(invalid_rows),
            "duplicates": duplicates,
            "invalid": invalid_rows,
            "stage_counts": stage_counts,
        }
        return {"valid_rows": valid_rows, "latest": latest_by_id, "quality": quality}

    def _decorate(self, row: dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        stage = self._text(item.get("花期阶段")) or self._bloom_stage(item)
        if stage not in STATUS_ORDER:
            stage = str(item.get("status") or STATUS_ORDER[0])
        item["花期阶段"] = stage
        item["status"] = stage
        item["造景状态"] = self._text(item.get("造景状态")) or stage

        cycle_days = self._cycle_days(item.get("换花周期"))
        item["换花周期(天)"] = cycle_days
        item["换花优先级"] = self._priority_label(self._priority_score(item))
        return item

    def _bloom_stage(self, row: dict[str, Any]) -> str:
        status = self._text(row.get("status"))
        if status in STATUS_ORDER:
            return status
        period = self._text(row.get("花期起止"))
        start, end = self._parse_period(period)
        if start is None or end is None:
            return STATUS_ORDER[0]
        today = date.today()
        if today < start:
            return "造景中"
        if today > end:
            return "已换花"
        span = (end - start).days
        elapsed = (today - start).days
        # 末段四分之一视为凋谢期，其余花期内视为盛花期。
        return "凋谢期" if span > 0 and elapsed >= span * 3 / 4 else "盛花期"

    def _parse_period(self, period: str) -> tuple[date | None, date | None]:
        pieces = re.findall(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", period)
        if len(pieces) < 2:
            return None, None
        parsed = []
        for piece in pieces[:2]:
            normalized = "-".join(part.zfill(2) for part in re.split(r"[-/.]", piece))
            try:
                parsed.append(date.fromisoformat(normalized))
            except ValueError:
                parsed.append(None)
        return parsed[0], parsed[1]

    def _cycle_days(self, value: Any) -> int | None:
        text = self._text(value)
        if not text:
            return None
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if not match:
            return None
        amount = float(match.group(1))
        for unit, days in UNIT_DAYS.items():
            if unit in text:
                return int(amount * days)
        return int(amount)

    def _priority_score(self, row: dict[str, Any]) -> float:
        days_value = row.get("换花周期(天)")
        if days_value is None and "换花周期(天)" not in row:
            days_value = self._cycle_days(row.get("换花周期"))
        days = float(days_value) if days_value is not None else math.inf
        if math.isinf(days):
            return math.inf
        stage = str(row.get("花期阶段") or row.get("status") or "")
        return days + STAGE_URGENCY.get(stage, 14)

    def _priority_sort_key(self, row: dict[str, Any]) -> tuple[float, int, int]:
        days_value = row.get("换花周期(天)")
        if days_value is None and "换花周期(天)" not in row:
            days_value = self._cycle_days(row.get("换花周期"))
        days = float(days_value) if days_value is not None else math.inf
        stage = str(row.get("花期阶段") or row.get("status") or "")
        return days, STAGE_URGENCY.get(stage, 14), int(row.get("id", 0))

    def _priority_label(self, score: float) -> str:
        if math.isinf(score):
            return "待确认"
        for limit, label in URGENCY_LABELS:
            if score <= limit:
                return label
        return "待确认"

    def _quality_item(self, row: dict[str, Any], reason: str) -> dict[str, Any]:
        return {
            "id": row.get("id"),
            "造景编号": row.get("造景编号", ""),
            "造景主题": row.get("造景主题", ""),
            "reason": reason,
        }

    def _text(self, value: Any) -> str:
        return str(value).strip() if value is not None else ""
