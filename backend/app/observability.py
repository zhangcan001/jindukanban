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
import threading
import time
import uuid
from collections import deque
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


REQUEST_ID_HEADER = "X-Request-ID"
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# 进程内 ring buffer——保留最近 N 条 WARNING+ 日志,供 /api/diagnostic/recent-errors 查询。
# 设计取舍:不写文件、不发外部 sink,只保留在内存里,避免给单机部署增加运维负担;
# 进程重启即清空,符合"现场临时排错"场景。
_LOG_BUFFER_CAPACITY = 200
_log_buffer: deque[dict[str, Any]] = deque(maxlen=_LOG_BUFFER_CAPACITY)
_log_buffer_lock = threading.Lock()


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


class RingBufferHandler(logging.Handler):
    """WARNING+ 日志同步写入 ``_log_buffer``,供诊断面板查询。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload: dict[str, Any] = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            rid = current_request_id()
            if rid:
                payload["request_id"] = rid
            for key, value in record.__dict__.items():
                if key in JsonLineFormatter._RESERVED_RECORD_KEYS or key.startswith("_"):
                    continue
                # extra={...} 里的字段做个浅 stringify,避免存放 ORM 对象引用导致内存泄漏
                try:
                    json.dumps(value, default=str)
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)
            if record.exc_info:
                payload["exc_info"] = logging.Formatter().formatException(record.exc_info)
            with _log_buffer_lock:
                _log_buffer.append(payload)
        except Exception:  # noqa: BLE001 — 日志路径不允许抛
            pass


def recent_log_entries(min_level: str = "WARNING", limit: int = 50) -> list[dict[str, Any]]:
    """返回 ring buffer 里的最近日志,新→旧 顺序。"""
    threshold = logging.getLevelName(min_level.upper())
    if not isinstance(threshold, int):
        threshold = logging.WARNING
    with _log_buffer_lock:
        snapshot = list(_log_buffer)
    filtered = [entry for entry in snapshot if logging.getLevelName(entry.get("level", "INFO")) >= threshold]
    return list(reversed(filtered[-limit:]))


def clear_log_buffer() -> int:
    """清空 ring buffer,返回清空前的条数(给诊断面板用)。"""
    with _log_buffer_lock:
        count = len(_log_buffer)
        _log_buffer.clear()
    return count


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

    # ring buffer 永远收 WARNING+,跟主 handler 的级别独立(主 handler 受 LOG_LEVEL 控制)
    ring = RingBufferHandler(level=logging.WARNING)
    root.addHandler(ring)
