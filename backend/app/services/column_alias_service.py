"""列名别名学习服务。

为表格列名识别提供"历史学习 + 模糊匹配"兜底机制：
1. 用户每次确认导入时，记录 (excel_column_name → system_field) 到 column_alias_history
2. 下次解析 Excel 时，若硬编码 FIELD_RULES 命中失败，依次尝试：
   - 精确匹配历史别名（按 hit_count 降序）
   - 模糊匹配历史别名（SequenceMatcher.ratio >= 阈值）

记录的范围分两级：
- project_id 不为 NULL: 仅在当前项目可见的别名
- project_id 为 NULL: 全局别名（导入到任何项目都可命中）

查询时按 (project_id, normalized_header, system_field) 唯一约束 upsert。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.column_alias_history import ColumnAliasHistory


FUZZY_MIN_RATIO = 0.75  # 低于此分数视为不匹配；中文短串 SequenceMatcher 在 0.7~0.8 区间最常见
HISTORY_FETCH_LIMIT = 200  # 单次 fuzzy 候选上限，避免 N+1 大量计算

# 监理表里常见的标点装饰（百分号、单位括号、连字符），不参与列名识别
_PUNCT_PATTERN = re.compile(r"[\s\(\)（）\[\]【】《》、，,\.。:：;；!！?？\-_\\/％%＊\*]+")


def normalize_header(value: str) -> str:
    """剥离空白与常见装饰性标点，再转小写。"""

    if not value:
        return ""
    return _PUNCT_PATTERN.sub("", str(value).strip().lower())


@dataclass
class AliasMatch:
    system_field: str
    field_type: str | None
    confidence: float  # 1.0=精确 / <1.0=模糊
    source: str  # "history-exact" | "history-fuzzy"


def record_alias(
    db: Session,
    *,
    project_id: int | None,
    raw_header: str,
    system_field: str,
    field_type: str | None = None,
) -> None:
    """upsert 一条别名记录。

    - 已存在相同 (project_id, normalized_header, system_field) 则 hit_count += 1
    - 否则新建，hit_count=1
    - last_used_at 更新为当前时间
    - 空 raw_header 或 system_field 直接跳过
    """

    if not raw_header or not system_field:
        return
    normalized = normalize_header(raw_header)
    if not normalized:
        return

    existing = db.execute(
        select(ColumnAliasHistory).where(
            ColumnAliasHistory.project_id.is_(project_id) if project_id is None else ColumnAliasHistory.project_id == project_id,
            ColumnAliasHistory.normalized_header == normalized,
            ColumnAliasHistory.system_field == system_field,
        )
    ).scalars().first()
    now = datetime.now()
    if existing is not None:
        existing.hit_count = (existing.hit_count or 0) + 1
        existing.last_used_at = now
        if field_type and not existing.field_type:
            existing.field_type = field_type
        if raw_header and existing.raw_header != raw_header:
            existing.raw_header = raw_header
        return

    db.add(
        ColumnAliasHistory(
            project_id=project_id,
            raw_header=raw_header,
            normalized_header=normalized,
            system_field=system_field,
            field_type=field_type,
            hit_count=1,
            last_used_at=now,
        )
    )
    db.flush()


def record_aliases_bulk(
    db: Session,
    *,
    project_id: int | None,
    mappings: list[tuple[str, str | None, str | None]],
) -> None:
    """批量记录，mappings 中每项为 (raw_header, system_field, field_type)；
    system_field 为 None 的条目跳过（用户未做映射）。"""

    for raw_header, system_field, field_type in mappings:
        if not system_field:
            continue
        record_alias(
            db,
            project_id=project_id,
            raw_header=raw_header,
            system_field=system_field,
            field_type=field_type,
        )


def lookup_alias(
    db: Session,
    *,
    project_id: int | None,
    raw_header: str,
) -> AliasMatch | None:
    """先尝试精确匹配，再尝试模糊匹配。

    精确：normalized_header 相等，按 hit_count 降序取第一条。
    模糊：在 project 范围 + 全局范围内取 HISTORY_FETCH_LIMIT 条 hot 数据，
          用 SequenceMatcher.ratio 评分，>= FUZZY_MIN_RATIO 则返回最高分。
    """

    normalized = normalize_header(raw_header)
    if not normalized:
        return None

    scope_clause = ColumnAliasHistory.project_id == project_id
    if project_id is not None:
        scope_clause = scope_clause | ColumnAliasHistory.project_id.is_(None)

    exact = db.execute(
        select(ColumnAliasHistory)
        .where(scope_clause, ColumnAliasHistory.normalized_header == normalized)
        .order_by(ColumnAliasHistory.hit_count.desc(), ColumnAliasHistory.last_used_at.desc().nullslast())
    ).scalars().first()
    if exact is not None:
        return AliasMatch(
            system_field=exact.system_field,
            field_type=exact.field_type,
            confidence=1.0,
            source="history-exact",
        )

    candidates = list(
        db.execute(
            select(ColumnAliasHistory)
            .where(scope_clause)
            .order_by(ColumnAliasHistory.hit_count.desc(), ColumnAliasHistory.last_used_at.desc().nullslast())
            .limit(HISTORY_FETCH_LIMIT)
        ).scalars()
    )
    best: tuple[float, ColumnAliasHistory] | None = None
    for row in candidates:
        ratio = SequenceMatcher(None, normalized, row.normalized_header).ratio()
        if ratio < FUZZY_MIN_RATIO:
            continue
        if best is None or ratio > best[0]:
            best = (ratio, row)

    if best is None:
        return None

    ratio, row = best
    return AliasMatch(
        system_field=row.system_field,
        field_type=row.field_type,
        confidence=round(ratio, 4),
        source="history-fuzzy",
    )


def enrich_columns_with_aliases(
    db: Session,
    *,
    project_id: int | None,
    columns: list[dict],
) -> list[dict]:
    """为列名识别结果补充别名历史结果。

    输入 columns 是 excel_parser.parse_preview 的输出。
    对 recommended_field 为 None 的列，尝试 lookup_alias，命中则填充：
    - recommended_field
    - field_type（若未识别）
    - alias_source / alias_confidence（新增字段，前端可用于显示"AI 建议"图标）
    - save_to_extra 同步变为 False
    - is_dimension / is_metric 根据 field_type 推断

    已经识别成功的列也会标 alias_source="rule"，方便前端统计。
    """

    if not columns:
        return columns

    enriched: list[dict] = []
    for column in columns:
        if column.get("recommended_field"):
            column.setdefault("alias_source", "rule")
            column.setdefault("alias_confidence", 1.0)
            enriched.append(column)
            continue
        match = lookup_alias(db, project_id=project_id, raw_header=str(column.get("name") or ""))
        if match is None:
            column.setdefault("alias_source", None)
            column.setdefault("alias_confidence", None)
            enriched.append(column)
            continue
        column["recommended_field"] = match.system_field
        if match.field_type and column.get("field_type") in (None, "unknown"):
            column["field_type"] = match.field_type
        column["alias_source"] = match.source
        column["alias_confidence"] = match.confidence
        column["save_to_extra"] = False
        field_type = column.get("field_type") or "unknown"
        column["is_dimension"] = field_type == "text"
        column["is_metric"] = field_type in {"number", "percent", "currency"}
        enriched.append(column)
    return enriched
