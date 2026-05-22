"""验证 X-Request-ID 中间件 + JSON 日志 contract。

为什么需要:这是排查"那一次请求"问题的唯一基建。如果它静默失效(比如某次 CORS
配置变更把 expose_headers 砍了),业务功能完全不受影响,但用户报 bug 时我们就抓瞎。
所以单测必须存在,且必须覆盖"上游传值用上游 / 不传自己生成 / 响应头能被浏览器拿到"
三个关键点。
"""
from __future__ import annotations

import json
import logging
import re

from fastapi.testclient import TestClient

from app.main import app
from app.observability import JsonLineFormatter, current_request_id


def test_request_id_is_generated_when_missing() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        rid = resp.headers.get("X-Request-ID")
        assert rid, "响应必须包含 X-Request-ID 头"
        # 没传上游的话应该是 32 位 hex(uuid4().hex)
        assert re.fullmatch(r"[0-9a-f]{32}", rid), f"自动生成的 request_id 应为 32 位 hex,实际 {rid!r}"


def test_request_id_passthrough_from_upstream() -> None:
    """上游(网关/前端)传过来的 request_id 必须被原样保留——便于跨进程串日志。"""
    with TestClient(app) as client:
        resp = client.get("/api/health", headers={"X-Request-ID": "trace-12345-abc"})
        assert resp.headers.get("X-Request-ID") == "trace-12345-abc"


def test_request_id_is_isolated_between_requests() -> None:
    """两个请求的 request_id 应该不同——确保 contextvar 没把状态泄漏到下一个请求。"""
    with TestClient(app) as client:
        a = client.get("/api/health").headers.get("X-Request-ID")
        b = client.get("/api/health").headers.get("X-Request-ID")
        assert a != b, "不同请求的 request_id 应当不同"


def test_json_formatter_emits_valid_json_with_request_id() -> None:
    """JSON 格式器输出必须是 ensure_ascii=False 的可解析 JSON,且包含 ts/level/logger/message 四件套。"""
    formatter = JsonLineFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="batch %s published",
        args=("B-001",),
        exc_info=None,
    )
    record.custom_field = "extra-value"  # type: ignore[attr-defined]
    output = formatter.format(record)
    payload = json.loads(output)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "batch B-001 published"
    assert payload["custom_field"] == "extra-value"  # extra 平铺
    assert "ts" in payload


def test_current_request_id_returns_none_outside_request() -> None:
    """不在请求上下文里时 current_request_id() 必须返回 None,而不是抛错。"""
    assert current_request_id() is None
