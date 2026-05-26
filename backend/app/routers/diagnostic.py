"""诊断面板 API——把进程内 ring buffer 暴露给前端。

为什么需要:之前用户遇到 ElMessage 红条,要看 traceback 必须登服务器翻 stderr。
现在前端"问题诊断"页面直接拉这个端点,把最近 WARNING/ERROR 日志展示出来,
现场操作人员提 bug 时可以一键截图。
"""
from __future__ import annotations

import os
import platform
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.config import get_settings
from app.observability import clear_log_buffer, recent_log_entries


router = APIRouter(prefix="/diagnostic", tags=["diagnostic"])


class LogEntry(BaseModel):
    ts: str
    level: str
    logger: str
    message: str
    request_id: str | None = None
    exc_info: str | None = None
    extra: dict[str, Any] = {}


class RecentLogsResponse(BaseModel):
    total: int
    entries: list[LogEntry]


class SystemInfo(BaseModel):
    app_name: str
    app_env: str
    log_level: str
    log_format: str
    python_version: str
    platform: str
    pid: int


class ClearLogsResponse(BaseModel):
    cleared: int


def _to_log_entry(payload: dict[str, Any]) -> LogEntry:
    known = {"ts", "level", "logger", "message", "request_id", "exc_info"}
    extra = {key: value for key, value in payload.items() if key not in known}
    return LogEntry(
        ts=str(payload.get("ts", "")),
        level=str(payload.get("level", "INFO")),
        logger=str(payload.get("logger", "")),
        message=str(payload.get("message", "")),
        request_id=payload.get("request_id"),
        exc_info=payload.get("exc_info"),
        extra=extra,
    )


@router.get("/recent-errors", response_model=RecentLogsResponse)
def get_recent_errors(
    level: str = Query("WARNING", description="最低级别,WARNING / ERROR / CRITICAL"),
    limit: int = Query(50, ge=1, le=200),
) -> RecentLogsResponse:
    entries = recent_log_entries(min_level=level, limit=limit)
    return RecentLogsResponse(total=len(entries), entries=[_to_log_entry(e) for e in entries])


@router.post("/clear-logs", response_model=ClearLogsResponse)
def clear_logs() -> ClearLogsResponse:
    return ClearLogsResponse(cleared=clear_log_buffer())


@router.get("/system-info", response_model=SystemInfo)
def get_system_info() -> SystemInfo:
    settings = get_settings()
    return SystemInfo(
        app_name=settings.app_name,
        app_env=settings.app_env,
        log_level=settings.log_level,
        log_format=settings.log_format,
        python_version=platform.python_version(),
        platform=f"{platform.system()} {platform.release()}",
        pid=os.getpid(),
    )
