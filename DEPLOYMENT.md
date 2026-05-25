# v3.4-final-stabilization 本地部署说明

本文档用于本地单机试用候选版交付。当前阶段不包含多人权限、PostgreSQL、Docker、安装包或新增 AI 功能。

本文已完成 v3.4-final-stabilization 文档一致性整理，适用于本地交付与回归验证。

## 1. 环境要求

1. Windows 10/11。
2. Python 3.12+。
3. Node.js 20+。
4. 项目目录保持完整，避免只复制 backend 或 frontend 的一部分。

## 2. 推荐启动方式

在项目根目录运行：

```bat
scripts\start.bat
```

脚本会：

- 检查项目根目录。
- 检查 `backend\.venv`。
- 检查后端依赖。
- 检查 `frontend\node_modules`。
- 检查后端和前端端口。
- 启动 FastAPI 后端。
- 等待 `/api/health` 健康检查通过。
- 启动 Vite 前端。
- 设置前端 API 地址为当前后端地址。
- 打开工作台首页。
- 在 `.runtime` 中记录本项目进程 PID，供 `stop.bat` 精准停止。

默认地址：

```text
后端 http://127.0.0.1:8000
前端 http://127.0.0.1:5173
```

## 2.1 portable 发布包

生成本地免安装发布包：

```bat
scripts\build_portable.bat
```

发布包位置：

```text
release\progress-dashboard-v3.4-final-stabilization
```

进入发布包后，可直接双击：

```text
start.bat
stop.bat
restart.bat
backup.bat
diagnose.bat
```

portable 包内默认数据目录：

```text
data/progress_dashboard.db
uploads/
exports/
backups/
logs/
```

迁移到另一台电脑时，建议先运行 `backup.bat`，再复制整个 `progress-dashboard-v3.4-final-stabilization` 文件夹，到新电脑后先运行 `diagnose.bat`，再运行 `start.bat`。

## 3. 停止与重启

```bat
scripts\stop.bat
scripts\restart.bat
```

`stop.bat` 只停止由 `start.bat` 记录的本项目 PID，不按端口直接误杀其他进程。若端口仍被占用，通常说明有手动启动的旧服务，需要手动关闭。

## 4. 手动启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

返回 `status=ok` 且数据库连接正常即表示后端可用。

## 5. 手动启动前端

```powershell
cd frontend
npm install
$env:VITE_API_BASE_URL='http://127.0.0.1:8000'
npm run dev -- --host 127.0.0.1 --port 5173
```

生产构建：

```powershell
cd frontend
npm run build
```

构建产物位于：

```text
frontend/dist/
```

## 6. 环境变量

本地正式版仍以 SQLite 为主：

```env
APP_NAME=progress-dashboard
APP_ENV=production
DATABASE_URL=sqlite:///./progress_dashboard.db
UPLOAD_DIR=uploads
EXPORT_DIR=reports
MAX_UPLOAD_SIZE_MB=20
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
LOG_LEVEL=INFO
```

说明：

- `DATABASE_URL`：SQLite 数据库连接。
- `UPLOAD_DIR`：上传文件目录。
- `EXPORT_DIR`：报表导出目录。
- `BACKEND_CORS_ORIGINS`：允许访问后端的前端地址。
- `VITE_API_BASE_URL`：前端请求后端的地址。

## 7. 数据目录

默认数据库：

```text
backend/progress_dashboard.db
```

默认上传目录：

```text
backend/uploads/
```

默认导出目录 / exports：

```text
backend/reports/
```

默认备份目录：

```text
backups/
```

如果使用相对路径，请从 `backend` 目录启动后端，避免数据库、上传文件或报表输出到错误位置。

## 8. 端口混用排查

若页面出现旧错误或 API 行为与测试不一致，优先检查：

```powershell
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 8000,5173 }
```

确认前端 `VITE_API_BASE_URL` 指向当前后端端口。旧后端残留是本地试运行中最常见的问题之一。

## 8.1 多 Sheet 导入部署确认

v3.4-final-stabilization 的多 Sheet 批量导入不需要额外服务。确认以下内容即可：

- 后端数据库可写，`import_batch` 可保存 `sheet_name`、`import_group_id`、`import_group_name` 和 `baseline_plan_id`。
- 上传目录可写，多个 Sheet 会复用同一个上传文件路径并生成独立批次。
- Dashboard `/analytics/trend` 返回 `data_date`、`sheet_name` 和 `status`，前端批次选择器据此区分同一天的多个 Sheet 批次。

## 8.2 本地数据维护确认

v3.4-final-stabilization 的项目归档、批次冻结、数据体检、备份记录、安全清理、维护日志和 Dashboard 进阶图表均基于本地 SQLite 与本机目录，不需要额外服务。

- 归档项目不会删除历史数据，默认限制新增导入、计划基线和整改项。
- 冻结批次不会影响 Dashboard 查看和报表导出，但会阻止同日期同 Sheet 覆盖、覆盖当前批次和人工修正。
- 安全清理默认先 dry-run 展示明细，正式执行前需再次确认。
- 备份记录只展示完整性和恢复说明，不自动恢复备份。

## 8.3 Dashboard 进阶图表确认

Dashboard V2 已整合进阶图表能力（专业进度、楼栋楼层热力、施工单位筛选等）通过 `/api/projects/{project_id}/analytics/dashboard-v2` 统一返回。当前看板 Excel 会随 `dashboard-export` 同步生成专业进度对比、楼层专业矩阵、楼栋专业矩阵和滞后分布统计 Sheet。

## 8.4 报表中心确认

v3.4-final-stabilization 的报表中心、报表预览、报表设置、报表历史筛选、导出 loading 和中文错误提示均基于现有 FastAPI、SQLite 与本地文件导出目录，不需要额外服务。Word 周报可按项目级 `report_config` 控制进阶图表分析、数据质量章节、整改闭环摘要和摘要条数。

## 9. 运行状态接口

```text
GET /api/maintenance/runtime-status
```

用于维护页显示当前版本、后端状态、数据库路径、上传目录、导出目录、备份目录、最近备份时间和数据数量。

## 10. 测试命令

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

```powershell
cd frontend
npm run build
```

## 11. 常见问题

- 后端无法启动：确认依赖安装完成，并从 `backend` 目录启动。
- 端口被占用：先运行 `scripts\stop.bat`；若仍占用，关闭手动启动的旧服务。
- 前端请求失败：确认 `VITE_API_BASE_URL` 与后端端口一致。
- 后端服务不可用，请确认系统已启动：确认后端已启动；刚启动时可等待几秒后刷新。
- 数据库不可写：确认项目目录有写权限。
- 上传失败：确认 `UPLOAD_DIR` 存在且可写。
- 报表导出失败：确认有已发布批次，且 `EXPORT_DIR` 可写。
- 备份失败：确认 `backups` 目录可写，并检查是否有文件被占用。





