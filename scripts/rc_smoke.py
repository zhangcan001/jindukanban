from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import httpx


BASE_URL = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "sample_progress_a.csv"
DOWNLOAD_DIR = ROOT / ".runtime" / "rc-smoke"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def request_json(method: str, path: str, **kwargs):
    response = httpx.request(method, f"{BASE_URL}{path}", timeout=60, **kwargs)
    response.raise_for_status()
    return response.json()


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def download(path: str, target: Path) -> None:
    response = httpx.get(f"{BASE_URL}{path}", timeout=120)
    response.raise_for_status()
    target.write_bytes(response.content)
    assert_true(target.exists() and target.stat().st_size > 0, f"download failed: {target}")


health = request_json("GET", "/api/health")
assert_true(health["status"] == "ok", "health failed")

project = request_json("POST", "/api/projects", json={"name": "v5.0-desktop-shell 整改闭环冒烟项目", "project_type": "测试"})
project_id = project["id"]

with SAMPLE.open("rb") as file:
    upload = request_json(
        "POST",
        f"/api/projects/{project_id}/imports/upload",
        data={"data_date": "2026-05-13"},
        files={"file": (SAMPLE.name, file, "text/csv")},
    )
batch_id = upload["batch"]["id"]
assert_true("CSV" in upload["sheets"], "CSV sheet missing")

parse = request_json(
    "POST",
    f"/api/imports/{batch_id}/parse",
    json={"sheet_name": "CSV", "header_row_index": 1, "data_start_row_index": 2},
)
assert_true(parse["batch"]["row_count"] >= 1, "parse returned no rows")

mappings = [
    {
        "excel_column_name": column["name"],
        "system_field_name": column.get("recommended_field"),
        "field_type": column.get("field_type") or "text",
        "is_dimension": bool(column.get("is_dimension")),
        "is_metric": bool(column.get("is_metric")),
        "save_to_extra": bool(column.get("save_to_extra")),
    }
    for column in parse["columns"]
]

mapping = request_json("POST", f"/api/imports/{batch_id}/mapping/validate", json={"field_mappings": mappings})
assert_true(mapping["valid"] is True, "mapping validation failed")

validation = request_json("POST", f"/api/imports/{batch_id}/validate", json={"field_mappings": mappings})
assert_true(validation["valid"] is True, "import validation failed")

confirm = request_json(
    "POST",
    f"/api/imports/{batch_id}/confirm",
    json={
        "save_as_template": True,
        "template_name": "rc-smoke-template",
        "data_date": "2026-05-14",
        "import_strategy": "new_batch",
        "field_mappings": mappings,
    },
)
assert_true(confirm["status"] == "imported", "confirm failed")
assert_true(confirm["imported_count"] >= 1, "no rows imported")

publish = request_json("POST", f"/api/imports/{batch_id}/publish")
assert_true(publish["status"] == "published", "publish failed")

overview = request_json("GET", f"/api/projects/{project_id}/analytics/overview", params={"batch_id": batch_id})
floor = request_json("GET", f"/api/projects/{project_id}/analytics/group-by", params={"dimension": "floor", "batch_id": batch_id})
building_floor = request_json("GET", f"/api/projects/{project_id}/analytics/building-floor", params={"batch_id": batch_id})
insight = request_json("GET", f"/api/projects/{project_id}/analytics/insight", params={"batch_id": batch_id})
assert_true(overview["item_count"] >= 1, "dashboard overview empty")
assert_true(len(floor["rows"]) >= 1, "floor statistics empty")
assert_true(len(building_floor["items"]) >= 1, "building floor statistics empty")
assert_true(bool(insight["overview_summary"]), "insight empty")

run_warnings = request_json("POST", f"/api/projects/{project_id}/warnings/run", params={"batch_id": batch_id})
warnings = request_json("GET", f"/api/projects/{project_id}/warnings", params={"batch_id": batch_id})
assert_true(run_warnings["generated_count"] >= 1, "warnings not generated")
assert_true(len(warnings) >= 1, "warning list empty")
located = next((row for row in warnings if row["building"] and row["floor"] and row["discipline"] and row["task_name"]), None)
assert_true(located is not None, "warning location missing")
assert_true(located["level_label"] not in {"critical", "warning", "info"}, "level not localized")
assert_true(located["status_label"] in {"未处理", "已处理", "已忽略"}, "status not localized")
for key in ("building", "floor", "task_name", "discipline"):
    assert_true(located[key] in located["warning_message"], f"warning message missing {key}")
assert_true(".0%" in located["warning_message"] or ".0 个百分点" in located["warning_message"], "percent precision missing")

building_filter = request_json(
    "GET",
    f"/api/projects/{project_id}/warnings",
    params={"batch_id": batch_id, "building": located["building"]},
)
floor_filter = request_json(
    "GET",
    f"/api/projects/{project_id}/warnings",
    params={"batch_id": batch_id, "floor": located["floor"]},
)
assert_true(len(building_filter) >= 1, "building filter failed")
assert_true(len(floor_filter) >= 1, "floor filter failed")

delayed = request_json("GET", f"/api/projects/{project_id}/analytics/delayed-ranking", params={"batch_id": batch_id})
assert_true(len(delayed["rows"]) >= 1, "delayed ranking empty")
delayed_source = delayed["rows"][0]
from_delayed = request_json(
    "POST",
    f"/api/projects/{project_id}/rectifications/from-progress-items",
    json={"batch_id": batch_id, "progress_item_id": delayed_source["progress_item_id"]},
)
assert_true(from_delayed["created"] is True, "rectification from delayed item not created")

from_warning = request_json(
    "POST",
    f"/api/projects/{project_id}/rectifications/from-warnings",
    json={"warning_record_id": located["id"]},
)
assert_true(from_warning["created"] is True, "rectification from warning not created")

rectification_ids = [from_delayed["item"]["id"], from_warning["item"]["id"]]
overdue_date = (date.today() - timedelta(days=1)).isoformat()
batch_update = request_json(
    "POST",
    f"/api/projects/{project_id}/rectifications/batch-update",
    json={
        "ids": rectification_ids,
        "status": "in_progress",
        "responsible_person": "RC责任人",
        "responsible_unit": "RC责任单位",
        "planned_finish_date": overdue_date,
        "remark": "v5.0-desktop-shell 批量整改回归",
    },
)
assert_true(batch_update["updated_count"] == len(rectification_ids), "batch update failed")

for target_status in ("completed", "closed", "ignored"):
    created = request_json(
        "POST",
        f"/api/projects/{project_id}/rectifications",
        json={
            "batch_id": batch_id,
            "source_type": "manual",
            "task_name": f"RC批量状态-{target_status}",
            "status": "open",
        },
    )
    updated = request_json(
        "POST",
        f"/api/projects/{project_id}/rectifications/batch-update",
        json={"ids": [created["id"]], "status": target_status},
    )
    assert_true(updated["updated_count"] == 1, f"batch status {target_status} failed")

rectifications = request_json(
    "GET",
    f"/api/projects/{project_id}/rectifications",
    params={"page": 1, "page_size": 1, "sort_by": "planned_finish_date", "sort_order": "asc"},
)
assert_true(rectifications["total"] >= 2 and len(rectifications["items"]) == 1, "rectification pagination failed")

overdue = request_json(
    "GET",
    f"/api/projects/{project_id}/rectifications",
    params={"batch_id": batch_id, "overdue": True},
)
assert_true(overdue["total"] >= 2, "overdue filter failed")
assert_true(all(row["is_overdue"] for row in overdue["items"]), "overdue flag mismatch")

person_filter = request_json(
    "GET",
    f"/api/projects/{project_id}/rectifications",
    params={"responsible_person": "RC责任人"},
)
unit_filter = request_json(
    "GET",
    f"/api/projects/{project_id}/rectifications",
    params={"responsible_unit": "RC责任单位"},
)
assert_true(person_filter["total"] >= 2, "responsible person filter failed")
assert_true(unit_filter["total"] >= 2, "responsible unit filter failed")

summary = request_json("GET", f"/api/projects/{project_id}/rectifications/summary", params={"batch_id": batch_id})
assert_true(summary["total"] >= 2 and summary["in_progress"] >= 2 and summary["overdue"] >= 2, "rectification summary failed")

logs = request_json("GET", f"/api/projects/{project_id}/rectifications/{rectification_ids[0]}/logs")
assert_true(any("批量更新" in (log.get("content") or "") for log in logs), "operation log missing batch update")

downloads = {
    "dashboard": DOWNLOAD_DIR / "dashboard.xlsx",
    "weekly": DOWNLOAD_DIR / "weekly.docx",
    "rectification": DOWNLOAD_DIR / "rectification.xlsx",
    "rectification_tracking": DOWNLOAD_DIR / "rectification-tracking.xlsx",
    "warnings": DOWNLOAD_DIR / "warnings.xlsx",
}
download(f"/api/projects/{project_id}/reports/dashboard-export?batch_id={batch_id}", downloads["dashboard"])
download(f"/api/projects/{project_id}/reports/weekly-word?batch_id={batch_id}", downloads["weekly"])
download(f"/api/projects/{project_id}/reports/delay-rectification-export?batch_id={batch_id}", downloads["rectification"])
download(f"/api/projects/{project_id}/rectifications/export?batch_id={batch_id}", downloads["rectification_tracking"])
download(f"/api/projects/{project_id}/warnings/export?batch_id={batch_id}", downloads["warnings"])

exports = request_json("GET", f"/api/projects/{project_id}/reports/exports")
assert_true(len(exports) >= 3, "report history missing")

runtime = request_json("GET", "/api/maintenance/runtime-status")
assert_true(runtime["portable_mode"] is True, "not portable mode")
normalized_database_path = runtime["database_path"].replace("/", "\\")
normalized_export_dir = runtime["export_dir"].replace("/", "\\")
assert_true(r"工程进度管理系统-v5.0-desktop-shell\app\data\progress_dashboard.db" in normalized_database_path, "database path not installer-lite data")
assert_true(r"工程进度管理系统-v5.0-desktop-shell\app\exports" in normalized_export_dir, "export path not installer-lite exports")

print(
    json.dumps(
        {
            "project_id": project_id,
            "batch_id": batch_id,
            "warning_count": len(warnings),
            "rectification_summary": summary,
            "exports_count": len(exports),
            "building_filter_count": len(building_filter),
            "floor_filter_count": len(floor_filter),
            "database_path": runtime["database_path"],
            "export_dir": runtime["export_dir"],
            "downloads": {name: str(path) for name, path in downloads.items()},
        },
        ensure_ascii=False,
        indent=2,
    )
)





