"""可观测性基建——X-Request-ID 中间件 + 结构化 JSON 日志。

为什么需要:之前用户反馈"刚才导出 Word 报告卡了"或者"批次发布报 500",我们只能
靠时间戳猜请求,日志里也没有把"那一次请求触发的所有日志"串到一起的办法。

设计:
- `RequestIdMiddleware`:每个 HTTP 请求生成或读取 X-Request-ID,放进 `contextvars`,
  并写回响应头。后续任何业务代码的 `logger.info(...)` 都会自动带上 request_id。
- `JsonLineFormatter`:把 logging.LogRecord 序列化成单行 JSON。生产环境下日志收集
  / 排查 / grep 都更容易;本地开发可以通过 `LOG_FORMAT=text` 切回人类可读格式。
- `configure_logging()`:启动时调用,把 root logger 的 handler 换成新格式器。
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


REQUEST_ID_HEADER = "X-Request-ID"
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    """返回当前请求上下文里的 request_id——业务代码一般用不到,日志格式器内部用。"""
    return _request_id_var.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        # 上游传过来的 ID 信任使用(便于跨进程串日志),否则自己生成
        request_id = incoming if incoming else uuid.uuid4().hex
        token = _request_id_var.set(request_id)
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            _request_id_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        elapsed_ms = (time.perf_counter() - start) * 1000
        logging.getLogger("request").info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": getattr(response, "status_code", None),
                "elapsed_ms": round(elapsed_ms, 2),
            },
        )
        return response


class JsonLineFormatter(logging.Formatter):
    """每条日志输出成一行 JSON——key 固定 + 业务可通过 extra={...} 注入字段。"""

    _RESERVED_RECORD_KEYS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = current_request_id()
        if request_id:
            payload["request_id"] = request_id
        # 把业务 extra={...} 的字段平铺进来,但跳过 LogRecord 自带的 reserved keys
        for key, value in record.__dict__.items():
            if key in self._RESERVED_RECORD_KEYS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """启动时调用一次——替换 root logger 的 handler。

    fmt="json"  → 一行 JSON,适合 prod 日志收集
    fmt="text"  → 传统可读格式,适合本地开发盯 stderr 的人
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # 先把 basicConfig 装上的 handler 全清掉,免得双倍输出
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    if fmt == "json":
        handler.setFormatter(JsonLineFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(handler)
