from __future__ import annotations

import re


FIELD_RULES: list[tuple[str, str, str]] = [
    (r"^(?:WBS|WBS编码|工作分解结构编码)$|_+(?:WBS|WBS编码|工作分解结构编码)$", "wbs_code", "text"),
    (r"^(?:任务编码|清单编码|编号|项目编码|task.?code)$", "task_code", "text"),
    (r"工作内容|施工内容|施工项|工序|工序内容|任务名称|子项|分项工程", "task_name", "text"),
    (r"父级|上级", "parent_task_name", "text"),
    (r"^(?:楼层|层|所在楼层|施工楼层|楼层/区域)$", "floor", "text"),
    (r"区域", "area", "text"),
    (r"^(?:施工单位|分包单位|责任单位|单位名称|承包单位)$", "construction_unit", "text"),
    (r"楼栋|单体|楼号|楼座", "building", "text"),
    (r"专业", "discipline", "text"),
    (r"系统", "system_name", "text"),
    (r"^(?:单位|计量单位|工程量单位|数量单位)$", "unit", "text"),
    (r"工程量|总工程量|设计量|合同量|清单量|总量|总数量", "total_quantity", "number"),
    (r"本周完成|本日完成|本月完成|本期完成|当期完成", "period_quantity", "number"),
    (r"累计完成量|累计完成|已完成量|完成工程量|累计工程量", "cumulative_quantity", "number"),
    (r"实际完成量", "actual_quantity", "number"),
    (r"剩余", "remaining_quantity", "number"),
    (r"计划完成量|应完成量|目标完成量", "planned_quantity", "number"),
    (r"计划进度|计划完成进度|目标进度|应完成进度|应完成率|本期计划进度|计划百分比|计划完成率", "planned_percent", "percent"),
    (
        r"实际进度|实际完成进度|完成进度|形象进度|实际形象进度|累计进度|累计完成率|完成百分比|完成比例|当前进度|施工进度|实际完成情况|完成情况|进度百分比|实际完成率",
        "actual_percent",
        "percent",
    ),
    (r"上报完成率", "reported_percent", "percent"),
    (r"计划开始", "planned_start_date", "date"),
    (r"计划完成|计划结束", "planned_finish_date", "date"),
    (r"实际开始", "actual_start_date", "date"),
    (r"实际完成日期|实际完成时间|实际结束|完成日期|完成时间", "actual_finish_date", "date"),
    (r"^(?:权重|任务权重|项目权重|统计权重|占比|weight)$", "weight", "number"),
    (r"权重", "weight", "number"),
    (r"产值|金额", "value_amount", "currency"),
    (r"状态", "status", "text"),
    (r"备注|说明", "remark", "text"),
    (r"责任人|负责人|责任工程师|班组|施工班组", None, "unknown"),
    (r"名称|清单名称", "task_name", "text"),
    (r"完成率", "actual_percent", "percent"),
]


def detect_column(column_name: str) -> dict[str, str | None]:
    normalized = re.sub(r"\s+", "", column_name)
    for pattern, system_field, field_type in FIELD_RULES:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return {"recommended_field": system_field, "field_type": field_type}
    return {"recommended_field": None, "field_type": "unknown"}
