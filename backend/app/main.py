from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import SessionLocal, check_database, init_db
from app.observability import RequestIdMiddleware, configure_logging
from app.routers import ai, analytics, baseline_plans, calculation_profiles, dashboard_v2, imports, maintenance, progress_items, projects, rectifications, reports, templates, warnings
from app.services.ai_service import ensure_builtin_prompt_templates
from app.services.project_template_service import ensure_builtin_project_templates


settings = get_settings()

configure_logging(level=settings.log_level, fmt=settings.log_format)

BACKEND_STARTED_AT: str | None = None
APP_VERSION = "v5.0-desktop-shell"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global BACKEND_STARTED_AT
    from datetime import datetime

    BACKEND_STARTED_AT = datetime.now().strftime("%Y-%m-%d %H:%M")
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.export_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.backup_dir).mkdir(parents=True, exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        ensure_builtin_project_templates(db)
        ensure_builtin_prompt_templates(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# 顺序很重要:RequestIdMiddleware 必须在 CORS 之后注册(Starlette 中间件按 LIFO 执行),
# 这样 X-Request-ID 在被 CORS 暴露给浏览器之前已经写入响应头。
dev_origin_regex = r"^http://(localhost|127\.0\.0\.1):\d+$" if settings.app_env == "development" else None

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=dev_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.include_router(projects.router, prefix=settings.api_prefix)
app.include_router(ai.router, prefix=settings.api_prefix)
app.include_router(calculation_profiles.router, prefix=settings.api_prefix)
app.include_router(baseline_plans.router, prefix=settings.api_prefix)
app.include_router(imports.router, prefix=settings.api_prefix)
app.include_router(analytics.router, prefix=settings.api_prefix)
app.include_router(dashboard_v2.router, prefix=settings.api_prefix)
app.include_router(progress_items.router, prefix=settings.api_prefix)
app.include_router(warnings.router, prefix=settings.api_prefix)
app.include_router(rectifications.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)
app.include_router(maintenance.router, prefix=settings.api_prefix)
app.include_router(templates.router, prefix=settings.api_prefix)


@app.get(f"{settings.api_prefix}/health")
def health_check() -> dict[str, str]:
    check_database()
    return {
        "status": "ok",
        "app": settings.app_name,
        "database": "connected",
    }


def _frontend_dist_dir() -> Path | None:
    backend_dir = Path(__file__).resolve().parents[1]
    candidates = [
        backend_dir.parent / "frontend_dist",
        backend_dir.parent / "frontend" / "dist",
    ]
    for candidate in candidates:
        if (candidate / "index.html").exists():
            return candidate
    return None


frontend_dist_dir = _frontend_dist_dir()
if frontend_dist_dir:
    assets_dir = frontend_dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")


@app.get("/")
def serve_frontend_index() -> FileResponse:
    if frontend_dist_dir is None:
        return FileResponse(Path(__file__).resolve().parents[1] / "README.md")
    return FileResponse(frontend_dist_dir / "index.html")


@app.get("/{full_path:path}")
def serve_frontend_fallback(full_path: str) -> FileResponse:
    if full_path == settings.api_prefix.strip("/") or full_path.startswith(f"{settings.api_prefix.strip('/')}/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    if frontend_dist_dir is None:
        return FileResponse(Path(__file__).resolve().parents[1] / "README.md")
    target = frontend_dist_dir / full_path
    frontend_root = frontend_dist_dir.resolve()
    if target.is_file() and target.resolve().is_relative_to(frontend_root):
        return FileResponse(target)
    return FileResponse(frontend_dist_dir / "index.html")






