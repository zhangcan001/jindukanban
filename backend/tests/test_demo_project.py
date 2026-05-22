from fastapi.testclient import TestClient

from app.main import app


def test_create_demo_project_creates_default_baseline() -> None:
    with TestClient(app) as client:
        response = client.post("/api/projects/demo")

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "示例项目 - 机电进度管理"
    assert payload["default_baseline_plan_id"] is not None


def test_create_demo_project_does_not_break_normal_project_creation() -> None:
    with TestClient(app) as client:
        demo_response = client.post("/api/projects/demo")
        normal_response = client.post("/api/projects", json={"name": "普通项目"})

    assert demo_response.status_code == 201
    assert normal_response.status_code == 201
    assert normal_response.json()["name"] == "普通项目"


def test_cleanup_test_projects_can_identify_demo_project() -> None:
    with TestClient(app) as client:
        client.post("/api/projects/demo")
        response = client.post("/api/maintenance/cleanup-test-projects")

    assert response.status_code == 200
    assert response.json()["matched_count"] >= 1
