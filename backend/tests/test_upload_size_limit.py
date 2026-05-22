"""D-P0b: 验证上传文件大小限制 (30MB)。"""
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app


def _make_oversized_xlsx_bytes(size_mb: int) -> bytes:
    """快速造一份 size_mb MB 大小的伪 xlsx 数据——不需要真的有效,大小到了就行。
    Upload 端点会先做大小检查,所以这里不需要 openpyxl 真能解析。"""
    # 31MB 全填 0x00,大约 31 * 1024 * 1024 字节
    return b"\x00" * (size_mb * 1024 * 1024)


def test_upload_rejects_file_over_30mb() -> None:
    with TestClient(app) as client:
        project_id = client.post("/api/projects", json={"name": "D-P0b 大文件拒绝测试"}).json()["id"]
        oversized = _make_oversized_xlsx_bytes(31)
        response = client.post(
            f"/api/projects/{project_id}/imports/upload",
            data={"data_date": "2026-05-22"},
            files={
                "file": (
                    "big.xlsx",
                    BytesIO(oversized),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert response.status_code == 413
    assert "30MB" in response.json()["detail"]
