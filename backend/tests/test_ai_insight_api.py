from datetime import date
import json
import socket
from io import BytesIO

from fastapi.testclient import TestClient
from docx import Document

from app.database import SessionLocal
from app.main import app
from app.models.import_batch import ImportBatch
from app.models.progress_item import ProgressItem
from app.models.project import Project
from app.models.rectification_item import RectificationItem


def _seed_project():
    db = SessionLocal()
    try:
        project = Project(name="AI 辅助测试项目")
        db.add(project)
        db.flush()
        batch = ImportBatch(project_id=project.id, file_name="ai.xlsx", status="published", data_date=date(2026, 5, 17), imported_count=2)
        db.add(batch)
        db.flush()
        db.add_all(
            [
                ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    task_name="喷淋支管安装",
                    building="A1",
                    floor="3层",
                    discipline="消防",
                    actual_percent=40,
                    planned_percent=70,
                    progress_deviation=-30,
                    status="seriously_delayed",
                ),
                ProgressItem(
                    project_id=project.id,
                    batch_id=batch.id,
                    task_name="桥架安装",
                    building="A1",
                    floor="4层",
                    discipline="机电",
                    actual_percent=80,
                    planned_percent=75,
                    progress_deviation=5,
                    status="ahead",
                ),
            ]
        )
        rectification = RectificationItem(
            project_id=project.id,
            batch_id=batch.id,
            source_type="manual",
            task_name="喷淋支管安装",
            issue_description="进度滞后",
            status="open",
            remark="原始备注",
        )
        db.add(rectification)
        db.commit()
        return project.id, batch.id, rectification.id
    finally:
        db.close()


def test_ai_insight_returns_rule_fallback_when_disabled() -> None:
    project_id, batch_id, _ = _seed_project()
    with TestClient(app) as client:
        response = client.post(f"/api/projects/{project_id}/ai/insight", json={"batch_id": batch_id, "mode": "dashboard_summary"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["source"] == "rule_fallback"
    assert payload["generated_text"] == payload["fallback_text"]


def test_ai_key_missing_does_not_return_500_or_secret() -> None:
    project_id, batch_id, _ = _seed_project()
    with TestClient(app) as client:
        config = client.put(
            f"/api/projects/{project_id}/ai/config",
            json={"enabled": True, "api_base_url": "http://127.0.0.1:9", "api_key": "", "model": "demo", "timeout_seconds": 1},
        )
        response = client.post(f"/api/projects/{project_id}/ai/insight", json={"batch_id": batch_id, "mode": "dashboard_summary"})

    assert config.status_code == 200
    assert config.json()["api_key_set"] is False
    assert response.status_code == 200
    assert response.json()["source"] == "rule_fallback"
    assert "api_key" not in json.dumps(response.json(), ensure_ascii=False)


def test_ai_call_failure_returns_fallback_and_does_not_expose_key() -> None:
    project_id, batch_id, _ = _seed_project()
    with TestClient(app) as client:
        client.put(
            f"/api/projects/{project_id}/ai/config",
            json={"enabled": True, "api_base_url": "http://127.0.0.1:9", "api_key": "secret-token", "model": "demo", "timeout_seconds": 1},
        )
        response = client.post(f"/api/projects/{project_id}/ai/insight", json={"batch_id": batch_id, "mode": "weekly_report_text"})

    assert response.status_code == 200
    body = json.dumps(response.json(), ensure_ascii=False)
    assert response.json()["source"] == "rule_fallback"
    assert "secret-token" not in body


class _FakeAiResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(
            {
                "choices": [{"message": {"content": "AI辅助生成：本期进度整体可控，消防专业需重点协调。"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7},
            },
            ensure_ascii=False,
        ).encode("utf-8")


def test_ai_success_returns_ai_and_writes_call_log_without_key(monkeypatch) -> None:
    project_id, batch_id, _ = _seed_project()
    monkeypatch.setattr("app.services.ai_service.urlrequest.urlopen", lambda *args, **kwargs: _FakeAiResponse())
    with TestClient(app) as client:
        client.put(
            f"/api/projects/{project_id}/ai/config",
            json={"enabled": True, "api_base_url": "http://example.test", "api_key": "secret-token", "model": "demo", "timeout_seconds": 5},
        )
        response = client.post(f"/api/projects/{project_id}/ai/insight", json={"batch_id": batch_id, "mode": "dashboard_summary"})
        logs_response = client.get(f"/api/projects/{project_id}/ai/logs")

    assert response.status_code == 200
    assert response.json()["source"] == "ai"
    assert "AI辅助生成" in response.json()["generated_text"]
    assert logs_response.status_code == 200
    logs_body = json.dumps(logs_response.json(), ensure_ascii=False)
    assert "secret-token" not in logs_body
    assert logs_response.json()[0]["source"] == "ai"
    assert logs_response.json()[0]["prompt_tokens"] == 11


def test_ai_timeout_returns_fallback(monkeypatch) -> None:
    project_id, batch_id, _ = _seed_project()

    def timeout(*args, **kwargs):
        raise socket.timeout("timed out")

    monkeypatch.setattr("app.services.ai_service.urlrequest.urlopen", timeout)
    with TestClient(app) as client:
        client.put(
            f"/api/projects/{project_id}/ai/config",
            json={"enabled": True, "api_base_url": "http://example.test", "api_key": "secret-token", "model": "demo", "timeout_seconds": 1},
        )
        response = client.post(f"/api/projects/{project_id}/ai/insight", json={"batch_id": batch_id, "mode": "dashboard_summary"})

    assert response.status_code == 200
    assert response.json()["source"] == "rule_fallback"
    assert "超时" in response.json()["error_message"]


def test_ai_insight_does_not_modify_business_data() -> None:
    project_id, batch_id, rectification_id = _seed_project()
    with TestClient(app) as client:
        before = client.get(f"/api/projects/{project_id}/rectifications/{rectification_id}").json()
        client.post(f"/api/projects/{project_id}/ai/insight", json={"batch_id": batch_id, "mode": "delay_reason_analysis"})
        after = client.get(f"/api/projects/{project_id}/rectifications/{rectification_id}").json()

    assert after["remark"] == before["remark"]
    assert after["status"] == before["status"]


def test_rectification_ai_suggestion_failure_does_not_modify_item() -> None:
    project_id, _, rectification_id = _seed_project()
    with TestClient(app) as client:
        response = client.post(f"/api/projects/{project_id}/ai/rectifications/{rectification_id}/suggestion")
        item = client.get(f"/api/projects/{project_id}/rectifications/{rectification_id}").json()

    assert response.status_code == 200
    assert response.json()["source"] == "rule_fallback"
    assert "喷淋支管安装" in response.json()["generated_text"]
    assert item["remark"] == "原始备注"


def test_weekly_word_without_ai_keeps_rule_text(monkeypatch) -> None:
    project_id, batch_id, _ = _seed_project()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("AI should not be called when weekly export does not request it")

    monkeypatch.setattr("app.services.report_service.generate_ai_text_with_logging", fail_if_called)
    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project_id}/reports/weekly-word", params={"batch_id": batch_id})

    assert response.status_code == 200
    assert response.content[:2] == b"PK"


def test_prompt_templates_read_copy_update_and_builtin_not_deleted() -> None:
    project_id, _, _ = _seed_project()
    with TestClient(app) as client:
        templates = client.get(f"/api/projects/{project_id}/ai/templates")
        builtin = next(item for item in templates.json() if item["code"] == "dashboard_summary" and item["is_builtin"])
        delete_builtin = client.delete(f"/api/projects/{project_id}/ai/templates/{builtin['id']}")
        copied = client.post(f"/api/projects/{project_id}/ai/templates/{builtin['id']}/copy")
        updated = client.patch(
            f"/api/projects/{project_id}/ai/templates/{copied.json()['id']}",
            json={"name": "自定义 Dashboard 模板", "prompt_template": "请生成测试分析", "is_active": True},
        )

    assert templates.status_code == 200
    assert len(templates.json()) >= 5
    assert delete_builtin.status_code == 400
    assert copied.status_code == 201
    assert copied.json()["is_builtin"] is False
    assert updated.status_code == 200
    assert updated.json()["name"] == "自定义 Dashboard 模板"


def test_weekly_word_with_ai_marks_ai_generated(monkeypatch) -> None:
    project_id, batch_id, _ = _seed_project()
    monkeypatch.setattr("app.services.ai_service.urlrequest.urlopen", lambda *args, **kwargs: _FakeAiResponse())
    with TestClient(app) as client:
        client.put(
            f"/api/projects/{project_id}/ai/config",
            json={"enabled": True, "api_base_url": "http://example.test", "api_key": "secret-token", "model": "demo", "timeout_seconds": 5},
        )
        response = client.get(f"/api/projects/{project_id}/reports/weekly-word", params={"batch_id": batch_id, "use_ai_text": "true"})

    assert response.status_code == 200
    document = Document(BytesIO(response.content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "AI辅助生成" in text


def test_rectification_ai_adopt_requires_explicit_update(monkeypatch) -> None:
    project_id, _, rectification_id = _seed_project()
    monkeypatch.setattr("app.services.ai_service.urlrequest.urlopen", lambda *args, **kwargs: _FakeAiResponse())
    with TestClient(app) as client:
        client.put(
            f"/api/projects/{project_id}/ai/config",
            json={"enabled": True, "api_base_url": "http://example.test", "api_key": "secret-token", "model": "demo", "timeout_seconds": 5},
        )
        suggestion = client.post(f"/api/projects/{project_id}/ai/rectifications/{rectification_id}/suggestion").json()
        before = client.get(f"/api/projects/{project_id}/rectifications/{rectification_id}").json()
        updated = client.patch(f"/api/projects/{project_id}/rectifications/{rectification_id}", json={"remark": suggestion["generated_text"]}).json()

    assert before["remark"] == "原始备注"
    assert updated["remark"] == suggestion["generated_text"]


def test_maintenance_ai_logs_endpoint_does_not_expose_key(monkeypatch) -> None:
    project_id, batch_id, _ = _seed_project()
    monkeypatch.setattr("app.services.ai_service.urlrequest.urlopen", lambda *args, **kwargs: _FakeAiResponse())
    with TestClient(app) as client:
        client.put(
            f"/api/projects/{project_id}/ai/config",
            json={"enabled": True, "api_base_url": "http://example.test", "api_key": "secret-token", "model": "demo", "timeout_seconds": 5},
        )
        client.post(f"/api/projects/{project_id}/ai/insight", json={"batch_id": batch_id, "mode": "dashboard_summary"})
        response = client.get("/api/maintenance/ai-logs")

    assert response.status_code == 200
    body = json.dumps(response.json(), ensure_ascii=False)
    assert "secret-token" not in body
    assert response.json()[0]["mode"] == "dashboard_summary"
