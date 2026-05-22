from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("FULL_AUTO_BASE_URL", "http://127.0.0.1:8000")
REPORT_DIR = ROOT / "test_reports"
SAMPLE_CANDIDATES = [
    ROOT / "sample_data" / "工程进度管理系统_全功能模拟测试表_v1.xlsx",
    ROOT / "工程进度管理系统_全功能模拟测试表_v1.xlsx",
]
SHEET_SINGLE = "01_单Sheet标准进度表"
SHEETS_MULTI = ["02_多Sheet_机电单位", "03_多Sheet_消防单位", "04_多Sheet_智能化单位"]
SHEET_ABNORMAL = "05_异常数据校验"
SHEET_MERGED = "06_合并表头样例"
SHEETS_NON_PROGRESS = ["07_非进度Sheet_字段检查", "08_非进度Sheet_问题记录"]
SHEET_HELPER = "09_计划基线测试"


@dataclass
class CheckItem:
    name: str
    status: str = "未执行"
    detail: str = ""
    level: str | None = None


@dataclass
class CheckState:
    checks: dict[str, CheckItem] = field(default_factory=dict)
    env_issues: list[str] = field(default_factory=list)
    p0: list[str] = field(default_factory=list)
    p1: list[str] = field(default_factory=list)
    p2: list[str] = field(default_factory=list)
    report_path: Path | None = None
    project_id: int | None = None
    baseline_id: int | None = None
    published_batch_ids: list[int] = field(default_factory=list)
    service_status: dict[str, str] = field(default_factory=dict)
    delayed_rectification: dict[str, str] = field(default_factory=dict)

    def set(self, key: str, status: str, detail: str = "", level: str | None = None) -> None:
        status = {"PASS": "通过", "FAIL": "失败", "SKIPPED": "跳过"}.get(status, status)
        self.checks[key] = CheckItem(key, status, detail, level)
        if status in {"失败", "无法自动验收", "未执行"} and level:
            getattr(self, level.lower()).append(f"{key}：{detail or status}")

    def env(self, message: str) -> None:
        self.env_issues.append(message)


class ApiError(RuntimeError):
    def __init__(self, method: str, path: str, status: int | None, body: str):
        super().__init__(f"{method} {path} failed: {status} {body[:300]}")
        self.method = method
        self.path = path
        self.status = status
        self.body = body


def request_json(method: str, path: str, payload: Any | None = None, params: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    url = build_url(path, params)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            content = response.read()
            if not content:
                return None
            return json.loads(content.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ApiError(method, path, exc.code, body) from exc
    except urllib.error.URLError as exc:
        raise ApiError(method, path, None, str(exc)) from exc


def request_bytes(method: str, path: str, params: dict[str, Any] | None = None) -> bytes:
    req = urllib.request.Request(build_url(path, params), method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ApiError(method, path, exc.code, body) from exc
    except urllib.error.URLError as exc:
        raise ApiError(method, path, None, str(exc)) from exc


def build_url(path: str, params: dict[str, Any] | None = None) -> str:
    url = f"{BASE_URL}{path}"
    if params:
        clean = {key: value for key, value in params.items() if value is not None}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)
    return url


def upload_file(project_id: int, file_path: Path, data_date: str) -> Any:
    boundary = f"----jindukanban{uuid4().hex}"
    file_bytes = file_path.read_bytes()
    parts: list[bytes] = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="data_date"\r\n\r\n')
    parts.append(data_date.encode("utf-8"))
    parts.append(b"\r\n")
    parts.append(f"--{boundary}\r\n".encode())
    disposition = f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
    parts.append(disposition.encode("utf-8"))
    parts.append(b"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n")
    parts.append(file_bytes)
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(
        build_url(f"/api/projects/{project_id}/imports/upload"),
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise ApiError("POST", f"/api/projects/{project_id}/imports/upload", exc.code, body_text) from exc
    except urllib.error.URLError as exc:
        raise ApiError("POST", f"/api/projects/{project_id}/imports/upload", None, str(exc)) from exc


def wait_health(seconds: int = 30) -> bool:
    for _ in range(seconds):
        try:
            payload = request_json("GET", "/api/health")
            if payload:
                return True
        except ApiError:
            time.sleep(1)
    return False


def mappings_from_columns(columns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mappings = []
    for index, column in enumerate(columns):
        field_name = column.get("recommended_field")
        if not field_name:
            continue
        mappings.append(
            {
                "excel_column_name": column["name"],
                "system_field_name": field_name,
                "field_type": column.get("field_type") or "text",
                "is_dimension": bool(column.get("is_dimension")),
                "is_metric": bool(column.get("is_metric")),
                "save_to_extra": bool(column.get("save_to_extra", True)),
                "sort_order": index,
            }
        )
    return mappings


def run_command(command: list[str], timeout: int = 300) -> tuple[bool, str]:
    try:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        output = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode == 0, output.strip()[-1200:]
    except Exception as exc:
        return False, str(exc)


def locate_sample() -> Path | None:
    for candidate in SAMPLE_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    state = CheckState()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    state.report_path = REPORT_DIR / f"full_auto_check_{timestamp}.md"
    state.service_status = {
        "preexisting": os.environ.get("FULL_AUTO_OLD_SERVICE_FOUND", "unknown"),
        "cleaned": os.environ.get("FULL_AUTO_OLD_SERVICE_CLEANED", "unknown"),
        "backend_pid": os.environ.get("FULL_AUTO_BACKEND_PID", "-"),
        "frontend_pid": os.environ.get("FULL_AUTO_FRONTEND_PID", "-"),
        "stopped_after": os.environ.get("FULL_AUTO_STOPPED_AFTER", "unknown"),
    }

    state.set("后端 health", "通过" if wait_health() else "失败", BASE_URL, "P0")
    state.set("pytest", os.environ.get("FULL_AUTO_PYTEST_STATUS", "未执行"), f"exit={os.environ.get('FULL_AUTO_PYTEST_EXIT', '-')}", "P0")
    state.set("npm run build", os.environ.get("FULL_AUTO_BUILD_STATUS", "未执行"), f"exit={os.environ.get('FULL_AUTO_BUILD_EXIT', '-')}", "P0")

    sample_path = locate_sample()
    if sample_path is None:
        message = "未找到全功能模拟测试表，请将文件放入 sample_data 目录。"
        state.env(message)
        for key in [
            "单 Sheet",
            "多 Sheet",
            "异常 Sheet",
            "合并表头 Sheet",
            "非进度 Sheet",
            "辅助 Sheet",
            "overview",
            "专业统计",
            "楼层统计",
            "楼栋楼层统计",
            "滞后项排行",
            "进阶图表",
            "运行预警",
            "预警记录",
            "楼栋楼层字段",
            "从滞后项生成",
            "从预警生成",
            "编辑责任信息",
            "状态流转",
            "操作记录",
            "当前看板 Excel",
            "Word 周报",
            "PDF 周报",
            "整改跟踪表",
            "报表历史",
        ]:
            state.set(key, "未执行", message)
        run_maintenance_checks(state)
        write_report(state)
        print(message)
        print(f"验收报告：{state.report_path}")
        return 2

    try:
        run_business_checks(state, sample_path)
    except Exception as exc:
        state.set("业务验收脚本", "失败", str(exc), "P0")
    finally:
        run_maintenance_checks(state)
        cleanup_project(state)
        write_report(state)

    print(f"验收报告：{state.report_path}")
    return 1 if state.p0 or state.p1 else 0


def run_business_checks(state: CheckState, sample_path: Path) -> None:
    project = request_json(
        "POST",
        "/api/projects",
        {
            "name": f"全功能自动化验收测试_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "project_type": "自动化验收",
            "owner_unit": "自动化验收建设单位",
            "supervision_unit": "自动化验收监理单位",
            "construction_unit": "自动化验收施工单位",
            "created_by": "full_auto_check",
        },
    )
    state.project_id = int(project["id"])
    baseline = request_json(
        "POST",
        f"/api/projects/{state.project_id}/baseline-plans",
        {
            "name": "全功能验收默认计划基线",
            "plan_type": "current",
            "description": "full_auto_check 自动创建",
            "baseline_date": date.today().isoformat(),
            "is_default": True,
            "is_active": True,
        },
    )
    state.baseline_id = int(baseline["id"])

    single_batch_id = import_single_sheet(state, sample_path)
    import_multi_sheets(state, sample_path)
    validate_negative_sheets(state, sample_path)
    run_dashboard_checks(state, single_batch_id)
    run_warning_checks(state, single_batch_id)
    run_rectification_checks(state, single_batch_id)
    run_report_checks(state, single_batch_id)


def import_single_sheet(state: CheckState, sample_path: Path) -> int:
    upload = upload_file(state.project_id or 0, sample_path, date.today().isoformat())
    batch_id = int(upload["batch"]["id"])
    parsed = request_json(
        "POST",
        f"/api/imports/{batch_id}/parse",
        {"sheet_name": SHEET_SINGLE, "header_row_index": None, "data_start_row_index": None, "baseline_plan_id": state.baseline_id},
    )
    mappings = mappings_from_columns(parsed["columns"])
    if not mappings:
        raise RuntimeError("单 Sheet 未识别到可用字段映射")
    validation = request_json("POST", f"/api/imports/{batch_id}/validate", {"field_mappings": mappings})
    confirm = request_json(
        "POST",
        f"/api/imports/{batch_id}/confirm",
        {
            "data_date": date.today().isoformat(),
            "baseline_plan_id": state.baseline_id,
            "import_strategy": "new_batch",
            "field_mappings": mappings,
        },
    )
    publish = request_json("POST", f"/api/imports/{batch_id}/publish")
    if not validation.get("valid") or confirm.get("imported_count", 0) <= 0 or publish.get("status") != "published":
        state.set("单 Sheet", "失败", f"valid={validation.get('valid')} imported={confirm.get('imported_count')}", "P0")
    else:
        state.set("单 Sheet", "通过", f"batch_id={batch_id} imported={confirm.get('imported_count')}")
    state.published_batch_ids.append(batch_id)
    return batch_id


def import_multi_sheets(state: CheckState, sample_path: Path) -> None:
    upload = upload_file(state.project_id or 0, sample_path, date.today().isoformat())
    file_id = int(upload["batch"]["id"])
    parsed = request_json(
        "POST",
        f"/api/imports/{file_id}/parse-multiple-sheets",
        {
            "project_id": state.project_id,
            "sheet_names": SHEETS_MULTI,
            "header_row_index": None,
            "data_start_row_index": None,
            "data_date": date.today().isoformat(),
            "baseline_plan_id": state.baseline_id,
        },
    )
    sheet_payloads = []
    for result in parsed.get("results", []):
        if result.get("status") != "parsed":
            continue
        mappings = mappings_from_columns(result.get("columns", []))
        if mappings:
            sheet_payloads.append({"batch_id": result["batch_id"], "sheet_name": result["sheet_name"], "mappings": mappings, "import_strategy": "new_batch"})
    if len(sheet_payloads) != len(SHEETS_MULTI):
        state.set("多 Sheet", "失败", f"解析成功 {len(sheet_payloads)}/{len(SHEETS_MULTI)}", "P1")
        return
    validation = request_json("POST", "/api/imports/validate-multiple-sheets", {"sheets": sheet_payloads})
    confirm = request_json(
        "POST",
        "/api/imports/confirm-multiple-sheets",
        {"project_id": state.project_id, "data_date": date.today().isoformat(), "baseline_plan_id": state.baseline_id, "sheets": sheet_payloads},
    )
    batch_ids = [item["batch_id"] for item in sheet_payloads]
    publish = request_json("POST", "/api/imports/publish-multiple-sheets", batch_ids)
    if validation.get("success_count") == len(SHEETS_MULTI) and confirm.get("success_count") == len(SHEETS_MULTI) and publish.get("published_count") == len(SHEETS_MULTI):
        state.set("多 Sheet", "通过", f"published={publish.get('published_count')}")
        state.published_batch_ids.extend(int(batch_id) for batch_id in batch_ids)
    else:
        state.set("多 Sheet", "失败", f"validation={validation.get('success_count')} confirm={confirm.get('success_count')} publish={publish.get('published_count')}", "P1")


def validate_negative_sheets(state: CheckState, sample_path: Path) -> None:
    check_unpublishable_sheet(state, sample_path, SHEET_ABNORMAL, "异常 Sheet", expect_validation_error=True)
    check_sheet_may_pass(state, sample_path, SHEET_MERGED, "合并表头 Sheet")
    for sheet in SHEETS_NON_PROGRESS:
        check_unpublishable_sheet(state, sample_path, sheet, "非进度 Sheet", expect_validation_error=False)
    check_unpublishable_sheet(state, sample_path, SHEET_HELPER, "辅助 Sheet", expect_validation_error=False)


def parse_sheet_for_check(state: CheckState, sample_path: Path, sheet_name: str) -> tuple[int, list[dict[str, Any]]]:
    upload = upload_file(state.project_id or 0, sample_path, date.today().isoformat())
    batch_id = int(upload["batch"]["id"])
    parsed = request_json("POST", f"/api/imports/{batch_id}/parse", {"sheet_name": sheet_name, "header_row_index": None, "data_start_row_index": None})
    return batch_id, mappings_from_columns(parsed.get("columns", []))


def check_unpublishable_sheet(state: CheckState, sample_path: Path, sheet_name: str, key: str, expect_validation_error: bool) -> None:
    try:
        batch_id, mappings = parse_sheet_for_check(state, sample_path, sheet_name)
        if not mappings:
            state.set(key, "通过", f"{sheet_name} 无可用字段映射，未发布")
            return
        validation = request_json("POST", f"/api/imports/{batch_id}/validate", {"field_mappings": mappings})
        confirm = request_json("POST", f"/api/imports/{batch_id}/confirm", {"import_strategy": "new_batch", "field_mappings": mappings})
        try:
            request_json("POST", f"/api/imports/{batch_id}/publish")
            state.set(key, "失败", f"{sheet_name} 被发布", "P1")
        except ApiError:
            if expect_validation_error and validation.get("valid") is True:
                state.set(key, "失败", f"{sheet_name} 未产生预期校验失败", "P1")
            else:
                existing = state.checks.get(key)
                detail = f"{sheet_name} valid={validation.get('valid')} imported={confirm.get('imported_count')}"
                if existing and existing.status == "通过" and existing.detail:
                    detail = existing.detail + "；" + detail
                state.set(key, "通过", detail)
    except ApiError as exc:
        state.set(key, "通过" if exc.status in {400, 404} else "失败", f"{sheet_name}: {exc}", None if exc.status in {400, 404} else "P1")


def check_sheet_may_pass(state: CheckState, sample_path: Path, sheet_name: str, key: str) -> None:
    try:
        batch_id, mappings = parse_sheet_for_check(state, sample_path, sheet_name)
        if not mappings:
            state.set(key, "失败", "合并表头样例未识别字段映射", "P2")
            return
        validation = request_json("POST", f"/api/imports/{batch_id}/validate", {"field_mappings": mappings})
        state.set(key, "通过" if validation.get("valid") else "失败", f"valid={validation.get('valid')} errors={validation.get('error_count')}", None if validation.get("valid") else "P2")
    except ApiError as exc:
        state.set(key, "失败", str(exc), "P2")


def run_dashboard_checks(state: CheckState, batch_id: int) -> None:
    calls = [
        ("overview", f"/api/projects/{state.project_id}/analytics/overview", {"batch_id": batch_id}, "P0"),
        ("专业统计", f"/api/projects/{state.project_id}/analytics/group-by", {"batch_id": batch_id, "dimension": "discipline"}, "P0"),
        ("楼层统计", f"/api/projects/{state.project_id}/analytics/group-by", {"batch_id": batch_id, "dimension": "floor"}, "P0"),
        ("楼栋楼层统计", f"/api/projects/{state.project_id}/analytics/building-floor", {"batch_id": batch_id}, "P0"),
        ("滞后项排行", f"/api/projects/{state.project_id}/analytics/delayed-ranking", {"batch_id": batch_id}, "P0"),
        ("进阶图表", f"/api/projects/{state.project_id}/analytics/dashboard-plus", {"batch_id": batch_id}, "P0"),
    ]
    for key, path, params, level in calls:
        try:
            payload = request_json("GET", path, params=params)
            state.set(key, "通过", summarize_payload(payload))
        except ApiError as exc:
            state.set(key, "失败", str(exc), level)


def run_warning_checks(state: CheckState, batch_id: int) -> None:
    try:
        result = request_json("POST", f"/api/projects/{state.project_id}/warnings/run", params={"batch_id": batch_id})
        state.set("运行预警", "通过" if result.get("generated_count", 0) >= 0 else "失败", f"generated={result.get('generated_count')}", "P1")
        records = request_json("GET", f"/api/projects/{state.project_id}/warnings", params={"batch_id": batch_id})
        state.set("预警记录", "通过" if isinstance(records, list) else "失败", f"count={len(records) if isinstance(records, list) else '-'}", "P1")
        fields_ok = any(all(record.get(field) for field in ("discipline", "building", "floor", "system_name", "task_name")) for record in records)
        state.set("楼栋楼层字段", "通过" if fields_ok or not records else "失败", "有预警时检查专业/楼栋/楼层/系统/施工项", "P1")
    except ApiError as exc:
        state.set("运行预警", "失败", str(exc), "P1")


def run_rectification_checks(state: CheckState, batch_id: int) -> None:
    warning_id = None
    try:
        delayed = request_json("GET", f"/api/projects/{state.project_id}/analytics/delayed-ranking", params={"batch_id": batch_id, "limit": 20})
        rows = delayed.get("rows", [])
        state.delayed_rectification["count"] = str(len(rows))
        state.set("滞后项数量", "通过" if rows else "失败", f"count={len(rows)}", "P1")
        delayed_row = rows[0] if rows else None
        delayed_id = delayed_row.get("progress_item_id") if delayed_row else None
        if delayed_id is None:
            detail = "验收样本未生成滞后项，请检查测试样本或 delayed-ranking 逻辑。"
            state.delayed_rectification["generated"] = "否"
            state.set("从滞后项生成", "失败", detail, "P1")
        else:
            created = request_json("POST", f"/api/projects/{state.project_id}/rectifications/from-progress-items", {"batch_id": batch_id, "progress_item_id": delayed_id})
            item = created["item"]
            item_id = item["id"]
            state.delayed_rectification["generated"] = "是"
            state.delayed_rectification["item_id"] = str(item_id)
            state.delayed_rectification["source_type"] = str(item.get("source_type", "-"))
            state.delayed_rectification["source_label"] = str(item.get("source_label", "-"))
            field_names = ("discipline", "building", "floor", "system_name", "task_name")
            missing = [name for name in field_names if not item.get(name)]
            source_ok = item.get("source_type") in {"progress_item", "delayed_item"}
            fields_ok = not missing
            state.set(
                "从滞后项生成",
                "通过" if created.get("item") and source_ok and fields_ok else "失败",
                f"item_id={item_id} source_type={item.get('source_type')} missing={','.join(missing) or 'none'}",
                None if created.get("item") and source_ok and fields_ok else "P1",
            )
            source_detail = f"source_type={item.get('source_type')} source_label={item.get('source_label')}"
            state.set("整改项来源标记", "通过" if source_ok else "失败", source_detail, None if source_ok else "P1")
            field_detail = " / ".join(str(item.get(name, "")) for name in field_names)
            state.set("整改项字段完整性", "通过" if fields_ok else "失败", field_detail if fields_ok else f"missing={','.join(missing)}", None if fields_ok else "P1")
            update_and_flow_rectification(state, item_id)
    except ApiError as exc:
        state.set("从滞后项生成", "失败", str(exc), "P1")

    try:
        records = request_json("GET", f"/api/projects/{state.project_id}/warnings", params={"batch_id": batch_id})
        warning_id = records[0].get("id") if records else None
        if warning_id is None:
            state.set("从预警生成", "无法自动验收", "当前数据没有预警记录，需要人工验证或补充样本", "P2")
        else:
            created = request_json("POST", f"/api/projects/{state.project_id}/rectifications/from-warnings", {"warning_record_id": warning_id})
            state.set("从预警生成", "通过", f"item_id={created['item']['id']}")
    except ApiError as exc:
        state.set("从预警生成", "失败", str(exc), "P1")


def update_and_flow_rectification(state: CheckState, item_id: int) -> None:
    finish_date = (date.today() + timedelta(days=7)).isoformat()
    try:
        updated = request_json(
            "PATCH",
            f"/api/projects/{state.project_id}/rectifications/{item_id}",
            {"responsible_person": "自动验收责任人", "responsible_unit": "自动验收责任单位", "planned_finish_date": finish_date},
        )
        state.set("编辑责任信息", "通过" if updated.get("responsible_person") == "自动验收责任人" else "失败", f"item_id={item_id}", "P1")
        for status in ["in_progress", "completed", "closed"]:
            request_json("POST", f"/api/projects/{state.project_id}/rectifications/{item_id}/status", {"status": status, "remark": f"自动验收状态流转 {status}"})
        state.set("状态流转", "通过", "open -> in_progress -> completed -> closed")
        logs = request_json("GET", f"/api/projects/{state.project_id}/rectifications/{item_id}/logs")
        log_count = len(logs) if isinstance(logs, list) else 0
        first_action = logs[0].get("action_label") if log_count else "-"
        state.delayed_rectification["logs"] = f"{log_count} 条（首条={first_action}）"
        state.set("操作记录", "通过" if logs else "失败", f"logs={log_count}", "P1")
    except ApiError as exc:
        state.set("状态流转", "失败", str(exc), "P1")


def run_report_checks(state: CheckState, batch_id: int) -> None:
    report_calls = [
        ("当前看板 Excel", f"/api/projects/{state.project_id}/reports/dashboard-export", {"batch_id": batch_id}, b"PK", "P0"),
        ("Word 周报", f"/api/projects/{state.project_id}/reports/weekly-word", {"batch_id": batch_id}, b"PK", "P1"),
        ("PDF 周报", f"/api/projects/{state.project_id}/reports/weekly-pdf", {"batch_id": batch_id}, b"%PDF", "P1"),
        ("整改跟踪表", f"/api/projects/{state.project_id}/rectifications/export", {"batch_id": batch_id}, b"PK", "P1"),
    ]
    for key, path, params, prefix, level in report_calls:
        try:
            data = request_bytes("GET", path, params=params)
            state.set(key, "通过" if data.startswith(prefix) else "失败", f"bytes={len(data)}", level)
        except ApiError as exc:
            state.set(key, "失败", str(exc), level)
    try:
        exports = request_json("GET", f"/api/projects/{state.project_id}/reports/exports")
        state.set("报表历史", "通过" if exports else "失败", f"count={len(exports) if isinstance(exports, list) else '-'}", "P1")
    except ApiError as exc:
        state.set("报表历史", "失败", str(exc), "P1")


def run_maintenance_checks(state: CheckState) -> None:
    try:
        health = request_json("GET", "/api/maintenance/data-health")
        state.set("data-health", "通过", summarize_payload(health))
    except ApiError as exc:
        state.set("data-health", "失败", str(exc), "P1")

    ok, output = run_command(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "backup.ps1"), "-Root", str(ROOT)], timeout=300)
    state.set("backup", "通过" if ok else "失败", output or "backup.ps1", "P1")

    ok, output = run_command(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "diagnose.ps1")], timeout=300)
    state.set("diagnose", "通过" if ok else "失败", output or "diagnose.ps1", "P2")


def cleanup_project(state: CheckState) -> None:
    if state.project_id is None:
        return
    try:
        request_json("DELETE", f"/api/projects/{state.project_id}/force", {"confirm_text": "确认删除项目"})
    except Exception:
        pass


def summarize_payload(payload: Any) -> str:
    if isinstance(payload, dict):
        parts = []
        for key in ("item_count", "batch_id", "count", "total", "project_count", "progress_item_count", "report_export_count"):
            if key in payload:
                parts.append(f"{key}={payload[key]}")
        return ", ".join(parts) or "响应正常"
    if isinstance(payload, list):
        return f"count={len(payload)}"
    return "响应正常"


def value(state: CheckState, key: str) -> str:
    item = state.checks.get(key)
    if not item:
        return "未执行"
    return f"{item.status}" + (f"（{item.detail}）" if item.detail else "")


def write_report(state: CheckState) -> None:
    passed = not state.env_issues and not state.p0 and not state.p1
    lines = [
        "## 全功能自动化验收报告",
        "",
        "### 一、基础检查",
        f"- 后端 health：{value(state, '后端 health')}",
        f"- pytest：{value(state, 'pytest')}",
        f"- npm run build：{value(state, 'npm run build')}",
        "",
        "### 二、导入验收",
        f"- 单 Sheet：{value(state, '单 Sheet')}",
        f"- 多 Sheet：{value(state, '多 Sheet')}",
        f"- 异常 Sheet：{value(state, '异常 Sheet')}",
        f"- 合并表头 Sheet：{value(state, '合并表头 Sheet')}",
        f"- 非进度 Sheet：{value(state, '非进度 Sheet')}",
        f"- 辅助 Sheet：{value(state, '辅助 Sheet')}",
        "",
        "### 三、Dashboard 验收",
        f"- overview：{value(state, 'overview')}",
        f"- 专业统计：{value(state, '专业统计')}",
        f"- 楼层统计：{value(state, '楼层统计')}",
        f"- 楼栋楼层统计：{value(state, '楼栋楼层统计')}",
        f"- 滞后项排行：{value(state, '滞后项排行')}",
        f"- 进阶图表：{value(state, '进阶图表')}",
        "",
        "### 四、预警验收",
        f"- 运行预警：{value(state, '运行预警')}",
        f"- 预警记录：{value(state, '预警记录')}",
        f"- 楼栋楼层字段：{value(state, '楼栋楼层字段')}",
        "",
        "### 五、整改闭环验收",
        f"- 滞后项数量：{value(state, '滞后项数量')}",
        f"- 从滞后项生成：{value(state, '从滞后项生成')}",
        f"- 整改项来源标记：{value(state, '整改项来源标记')}",
        f"- 整改项字段完整性：{value(state, '整改项字段完整性')}",
        f"- 从预警生成：{value(state, '从预警生成')}",
        f"- 编辑责任信息：{value(state, '编辑责任信息')}",
        f"- 状态流转：{value(state, '状态流转')}",
        f"- 操作记录：{value(state, '操作记录')}",
        "",
        "### 六、服务状态",
        f"- 启动前是否存在旧服务：{state.service_status.get('preexisting', 'unknown')}",
        f"- 是否清理本项目旧服务：{state.service_status.get('cleaned', 'unknown')}",
        f"- 后端 PID：{state.service_status.get('backend_pid', '-')}",
        f"- 前端 PID：{state.service_status.get('frontend_pid', '-')}",
        f"- 结束后是否停止：{state.service_status.get('stopped_after', 'unknown')}",
        "",
        "### 七、滞后整改验收",
        f"- 滞后项数量：{state.delayed_rectification.get('count', '-')}",
        f"- 是否从滞后项生成整改项：{state.delayed_rectification.get('generated', '-')}",
        f"- 整改项 ID：{state.delayed_rectification.get('item_id', '-')}",
        f"- 操作记录：{state.delayed_rectification.get('logs', '-')}",
        "",
        "### 八、报表验收",
        f"- 当前看板 Excel：{value(state, '当前看板 Excel')}",
        f"- Word 周报：{value(state, 'Word 周报')}",
        f"- PDF 周报：{value(state, 'PDF 周报')}",
        f"- 整改跟踪表：{value(state, '整改跟踪表')}",
        f"- 报表历史：{value(state, '报表历史')}",
        "",
        "### 九、系统维护验收",
        f"- data-health：{value(state, 'data-health')}",
        f"- backup：{value(state, 'backup')}",
        f"- diagnose：{value(state, 'diagnose')}",
        "",
        "### 十、问题分级",
        "- 环境问题：" + ("；".join(state.env_issues) if state.env_issues else "无"),
        "- P0：" + ("；".join(state.p0) if state.p0 else "无"),
        "- P1：" + ("；".join(state.p1) if state.p1 else "无"),
        "- P2：" + ("；".join(state.p2) if state.p2 else "无"),
        "",
        "### 十一、结论",
        f"- 是否通过：{'是' if passed else '否'}",
        f"- 是否可发布：{'是' if passed else '否'}",
        "",
    ]
    assert state.report_path is not None
    state.report_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
