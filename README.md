# 工程进度看板

当前推荐版本：v4.9-exe-launcher  
上一版本：v4.8.4-final-package-refresh

定位：本地单机便携版工程进度管理系统。v4.9-exe-launcher 聚焦 Windows 可移植 EXE 启动包，采用“文件夹 + EXE 启动器”交付方式；不改变 Excel 导入、字段识别、进度计算、Dashboard V2 统计或报表导出逻辑。

当前开发节奏：

从 v2.9 起采用快速迭代模式：

- 功能开发
- 快速发布
- 不再默认拆 alpha / beta / rc / release
- 仅 P0/P1 阻塞发布

v4.9-exe-launcher 当前核心能力：

- 单 Sheet / 多 Sheet Excel 导入
- 字段识别和字段映射模板
- 计划基线
- Dashboard V2 默认看板和旧版兼容看板
- Dashboard V2 总体 / 专业 / 楼栋三视图
- 权重归一化统计
- full_auto_check 全功能自动验收
- Windows 可移植 EXE 启动包
- installer-lite 安装包本地运行
- 备份 / 恢复 / 诊断
- 预警记录
- 整改闭环
- 报表中心
- AI 辅助分析
- 本地备份 / 诊断 / portable 包
- 数据维护
- 示例项目
- sample_data 示例 Excel
- 新手引导页

本项目是面向本地单机使用的工程进度管理工具。后端使用 FastAPI + SQLAlchemy + SQLite，前端使用 Vue 3 + TypeScript + Vite + Element Plus + ECharts。

从 T037 起，系统默认使用 Dashboard V2。Dashboard V2 支持总体视图、专业视图、楼栋视图、楼层热力图、权重归一化统计、统一筛选口径和统一图表数据来源；旧版 Dashboard 仅作为历史兼容入口保留。

适用场景：

- 单人本地使用
- 导入 Excel 进度表
- 查看工程进度看板
- 楼层 / 楼栋楼层统计
- 预警记录
- Word 周报
- 整改清单
- 整改闭环跟踪
- 本地备份
- 便携迁移

## 当前支持

- 本地单机使用
- Excel 导入
- 单 Sheet 导入
- 多 Sheet 批量导入
- 每个 Sheet 独立解析 / 校验 / 导入
- 每个 Sheet 独立生成导入批次
- 多 Sheet 批量发布
- 多 Sheet 结果汇总和 Sheet 级失败隔离
- 字段识别
- 导入校验
- 看板分析
- 计划基线管理
- 导入批次绑定计划基线
- Dashboard V2 默认进度看板
- Dashboard / 报表显示当前计划基线
- 规则化进度分析说明
- 楼层统计
- 楼栋楼层统计
- 滞后项说明
- 当前看板 Excel 导出
- Word 周报导出
- 滞后项整改清单导出
- 整改项列表、筛选、排序、分页
- 从滞后项 / 预警记录生成整改项
- 整改项批量更新状态、责任人、责任单位和计划完成时间
- 逾期整改项判断与筛选
- 整改操作记录
- Dashboard / Word 周报 / 当前看板 Excel 整改摘要
- 整改跟踪表导出
- 报表历史
- 本地备份
- 系统维护
- 项目归档 / 恢复
- 批次冻结 / 取消冻结
- 冻结批次覆盖保护
- 数据体检
- 备份记录完整性检查
- 安全清理 dry-run
- 维护日志
- 报表显示项目状态 / 批次状态
- 项目模板
- 字段映射模板
- 模板推荐
- 模板匹配度
- 一键套用模板
- 保存当前映射为模板
- 模板管理页
- 内置机电 / 消防 / 智能化 / 通用模板
- 统计口径模板
- 预警规则模板
- Dashboard 进度分析说明模块
- Dashboard V2 总体视图
- Dashboard V2 专业视图
- Dashboard V2 楼栋视图
- Dashboard V2 楼层热力图
- Dashboard V2 权重归一化统计
- Dashboard V2 统一筛选口径
- Dashboard V2 统一图表数据来源
- Word 周报进度分析说明
- 当前看板 Excel 进度分析说明 Sheet
- 专业进度对比图
- 楼层专业矩阵
- 楼栋专业矩阵
- 滞后分布统计
- 全系统 loading / 空状态 / 失败提示优化
- 大数据表格默认分页和长文本悬停显示
- 导出耗时提示、完成提示和后端 message 透传
- AI 辅助生成标注、失败 fallback 和 API Key 脱敏
- Dashboard 进阶图表筛选
- 图表点击查看明细
- 当前看板 Excel 进阶图表 Sheet
- 报表中心报表卡片
- 报表预览
- 报表设置
- Word 周报进阶图表分析
- 报表历史筛选
- 导出失败中文提示
- 无楼层 / 无楼栋 / 无计划进度空状态
- 本地 portable 发布包
- `scripts\build_portable.bat`
- `scripts\diagnose.bat`
- portable 数据目录
- portable 备份目录
- 预警记录楼栋楼层增强
- 预警详情增强
- 预警筛选增强
- 便携版诊断日志
- 本地迁移说明

## 当前限制

- 暂不提供安装程序
- 暂不打包 Python 运行时
- 暂不打包 Node 运行时
- 暂不支持多人权限
- 暂不支持 PostgreSQL
- 暂不支持 Docker
- 暂不新增业务模块
- 暂不扩展 AI 功能
- 暂不做自定义图表保存
- 暂不做大屏模式
- 暂不做图表拖拽布局
- 暂不做 AI 图表解读
- 暂不做自定义 Word 模板编辑器
- 暂不做 PDF 导出
- 暂不做 AI 报告润色
- 暂不做云端报表共享
- 暂不自动恢复备份
- 暂不做危险删除
- 暂不支持多用户
- 暂不支持云同步
- 暂不支持移动端 App
- 暂不做跨 Sheet 自动合并
- 暂不做同一 Sheet 多表格识别
- 暂不做多 Sheet 去重合并
- 暂不做异步大文件导入
- 暂不支持模板版本管理
- 暂不支持多人共享模板
- 暂不支持云端模板库
- 暂不支持 AI 自动生成模板
- 当前主要面向本地单机使用

## 技术栈

- 后端：FastAPI、SQLAlchemy 2.x、SQLite、Pydantic Settings、openpyxl、python-docx、pandas。
- 前端：Vue 3、TypeScript、Vite、Element Plus、ECharts。
- 测试：pytest、FastAPI TestClient、TypeScript、Vite build。

## 目录结构

```text
backend/          FastAPI 后端
backend/app/      后端模型、路由、服务和配置
backend/uploads/  默认上传文件目录
backend/reports/  默认报表导出目录
frontend/         Vue 前端
sample_data/      示例 Excel 和导入说明
samples/          CSV 样例
scripts/          本地启动、停止、重启、备份脚本
backups/          本地备份输出目录
```

## 模板库

v1.6-template 新增模板库能力，适合本地长期重复导入同类 Excel 时减少配置工作。

项目模板：

- 机电安装项目模板
- 消防工程项目模板
- 智能化工程项目模板
- 通用进度项目模板

新建项目时可以选择模板。选择后系统会自动生成默认统计口径、默认预警规则、默认看板配置和默认报表配置。不选择模板时保持原有新建项目流程。

字段映射模板：

- 字段映射页会按 Excel 表头推荐历史模板。
- 推荐模板显示匹配度。
- 用户可以一键套用模板。
- 正式导入时可以保存当前映射为模板。
- 模板管理页支持查看、复制、重命名、启用/停用和删除自建模板。

模板管理页：

```text
http://127.0.0.1:5173/templates
```

## 多 Sheet 批量导入

v3.1-import-usability 支持同一个 Excel 文件内勾选多个 Sheet，并按 Sheet 独立完成解析、字段映射、校验、确认导入和发布；本次只优化导入流程提示、Sheet 推荐、字段映射提示、校验结果分组、结果汇总和失败重试体验，不改 Excel 导入核心逻辑。

关键规则：

- 每个 Sheet 独立生成一个 `import_batch`。
- 多 Sheet 导入会写入 `import_group_id` 和 `import_group_name`，用于标识同一次导入。
- `replace_same_date` 只替换同一 `project_id + data_date + sheet_name` 的旧批次，不同 Sheet 不会互相停用。
- 批量发布只发布已导入成功的批次，失败 Sheet 会被跳过并显示失败原因。
- Dashboard 批次选择器显示 `data_date｜sheet_name｜发布状态`，同一天多个 Sheet 批次也可区分。
- 当前限制是不做跨 Sheet 自动合并、不做同一 Sheet 多表格识别、不做多 Sheet 去重合并、不做异步大文件导入。

## 进度分析说明

v1.7-insight-rc 新增规则化进度分析说明，用于在不接入 AI 的前提下，将现有进度数据整理为更适合监理周报和现场协调会使用的文字说明。

分析说明基于：

- 总体实际完成率、计划完成率和进度偏差
- 分专业统计
- 楼层统计
- 楼栋楼层统计
- 滞后项排行
- 数据质量评分和校验问题

输出内容包括：

- 总体进度说明
- 主要滞后专业
- 主要滞后楼层
- 楼栋楼层说明
- 主要滞后施工项
- 数据质量说明
- 本期关注事项
- 建议措施

接口：

```text
GET /api/projects/{project_id}/analytics/insight
```

说明：

- 完全基于规则生成，不调用外部模型。
- 切换批次、统计口径、计划基线和楼栋后，Dashboard 自动刷新分析说明。
- Word 周报和当前看板 Excel 使用同一套规则结果，避免多处文案不一致。

## 一键启动

开发 / 本地启动推荐方式：

方式一，推荐：

```bat
scripts\dev_start.bat
```

或：

```bat
npm run dev:all
```

该命令会自动检查并启动后端，然后启动前端。

方式二，手动启动：

先启动后端，再启动前端。具体命令见下方“手动启动”。

在项目根目录运行：

```bat
scripts\start.bat
```

默认地址：

- 后端：http://127.0.0.1:8000
- 前端：http://127.0.0.1:5173

停止服务：

```bat
scripts\stop.bat
```

重启服务：

```bat
scripts\restart.bat
```

## 本地桌面化使用

v1.8-desktop-rc 重点增强本地单机长期使用体验，让系统更接近“本地电脑上的一个软件”。

启动系统：

```bat
scripts\dev_start.bat
```

开发启动脚本会先检查 `http://127.0.0.1:8000/api/health`。如果后端已运行，会显示“后端已运行，跳过启动。”并复用现有后端；如果后端未运行，会自动启动后端、等待健康检查通过，再启动前端并打开浏览器。

也可以使用原有本地启动脚本：

```bat
scripts\start.bat
```

启动脚本会检查后端虚拟环境、后端依赖、前端依赖、端口占用，并在后端健康检查通过后启动前端和打开浏览器。

关闭系统：

```bat
scripts\stop.bat
```

停止脚本优先读取 `.runtime\backend.pid` 和 `.runtime\frontend.pid`，只停止本项目启动的进程，不会批量结束其它 Python 或 Node 进程。

重启系统：

```bat
scripts\restart.bat
```

备份数据：

```bat
scripts\backup.bat
```

备份内容包括 SQLite 数据库、uploads 上传文件、reports 导出报表和报表历史相关文件。备份目录格式：

```text
backups\backup_YYYYMMDD_HHMMSS
```

查看恢复说明：

```bat
scripts\restore_guide.bat
```

恢复脚本只显示步骤，不会自动覆盖数据。恢复前应先关闭系统，并再次备份当前数据。

数据保存位置：

- 数据库：`backend\progress_dashboard.db`
- 上传文件：`backend\uploads`
- 导出报表 / exports：`backend\reports`
- 备份目录：`backups`

常见本地问题：

- 端口被占用：先运行 `scripts\stop.bat`；如果仍被占用，请手动关闭旧服务或更换端口。
- 后端启动失败：检查 `backend\.venv` 是否存在，并确认已安装 `backend\requirements.txt`。
- 前端打不开：确认 `frontend\node_modules` 存在，并查看 `.runtime\frontend.err.log`。
- 无法连接后端服务：确认已运行 `scripts\dev_start.bat` 或 `scripts\start.bat`；刚启动时可等待几秒后刷新。
- 当前项目不存在或已被清理：请回到项目列表重新选择。
- 报表导出失败：确认存在已发布批次，并检查 `backend\reports` 是否可写。
- 备份目录找不到：先运行 `scripts\backup.bat`，或在维护页复制备份目录路径。

## 本地免安装发布包

v3.9-demo-onboarding 保留本地免安装发布包能力，并随包提供 sample_data 示例 Excel、新手引导页和帮助中心说明。

生成发布包：

```bat
scripts\build_portable.bat
```

发布包位置：

```text
release\progress-dashboard-v3.9-demo-onboarding
```

启动发布包：

```text
双击 start.bat
```

停止发布包：

```text
双击 stop.bat
```

备份发布包数据：

```text
双击 backup.bat
```

诊断本机环境：

```text
双击 diagnose.bat
```

便携版数据目录：

- 数据库：`data\progress_dashboard.db`
- 上传文件：`uploads\`
- 导出报表：`exports\`
- 备份：`backups\`
- 诊断日志：`logs\`

迁移到另一台电脑：

1. 先运行 `stop.bat` 停止系统。
2. 运行 `backup.bat` 备份当前数据。
3. 复制整个 `progress-dashboard-v3.9-demo-onboarding` 文件夹到新电脑。
4. 在新电脑运行 `diagnose.bat` 检查 Python、端口、数据目录和健康状态。
5. 再运行 `start.bat` 启动系统。

便携版常见问题：

- 端口被占用：运行 `stop.bat`；如果仍占用，请手动关闭旧服务或调整端口。后端默认端口为 `8000`，前端默认端口为 `5173`。脚本不会自动结束非本项目进程；可以关闭占用程序，或临时指定端口后启动：

```bat
set BACKEND_PORT=8028
set FRONTEND_PORT=5228
start.bat
```

- Python 不可用：安装 Python 3.12+，或确认 Python 在 PATH 中。
- Node 不可用：便携版运行不依赖 Node；只有重新构建前端时需要 Node。
- 后端启动失败：检查 `backend\.venv` 和 `backend\.env`。
- `frontend_dist` 不存在：在源码目录先运行 `npm run build`，再执行 `scripts\build_portable.bat`。
- 数据库不存在：首次启动会自动创建。
- 报表导出失败：检查 `exports` 目录是否可写。
- 浏览器打不开：手动访问 `http://127.0.0.1:5173`。

## 手动启动

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm install
$env:VITE_API_BASE_URL='http://127.0.0.1:8000'
npm run dev -- --host 127.0.0.1 --port 5173
```

健康检查：

```text
GET http://127.0.0.1:8000/api/health
```

## 使用流程

1. 打开工作台。
2. 创建或选择项目。
3. 导入 Excel。
4. 选择 Sheet。
5. 解析表头。
6. 完成字段映射。
7. 执行导入校验。
8. 确认导入。
9. 发布批次。
10. 查看 Dashboard、楼层统计、楼栋楼层统计、滞后项排行和进度明细。
11. 导出当前看板 Excel、Word 周报和滞后项整改清单。
12. 在报表历史查看导出记录。
13. 在系统维护页查看本地路径、数据数量和备份命令。

## 报表导出

当前稳定支持 3 类核心导出：

- 当前看板 Excel：包含看板总览、专业进度统计、楼层进度统计、楼栋楼层统计、滞后项清单、数据质量与校验问题汇总、进度分析说明。
- Word 周报：包含工程进度周报标题、基础信息表、总体进度概况、重点指标表、分专业进度、楼层进度、楼栋楼层进度、主要滞后项、数据质量与校验问题、进度分析说明、导出时间。
- 滞后项整改清单：包含专业、楼栋、楼层、系统、施工项、实际完成率、计划完成率、偏差、滞后等级、滞后说明、整改建议、责任人、计划完成时间、复查结果、备注。

统一 report_type：

```text
dashboard_excel
weekly_word
delay_rectification_excel
```

## 系统维护

访问：

```text
http://127.0.0.1:5173/maintenance
```

维护页显示数据库路径、上传目录、导出目录、项目数量、导入批次数、进度明细数量、报表导出数量和备份命令说明。

v1.8-desktop-rc 起，维护页增加“本地运行状态”，显示当前版本、后端状态、数据库状态、最近备份时间、数据库路径、上传目录、导出目录和备份目录，并提供路径复制和恢复说明。没有备份记录时显示“暂无备份记录”。

清理规则：

- 清理未发布批次不影响 published 批次。
- 清理测试项目只匹配名称包含“测试、test、demo、样例、示例”的项目。
- 清理前会二次确认。
- 当前项目被清理后会恢复到剩余项目；没有剩余项目时回到未选择项目状态。

## 本地备份

```bat
scripts\backup.bat
```

备份输出到：

```text
backups\backup_yyyy-MM-dd_HHmmss\
```

备份内容：

- SQLite 数据库
- uploads 上传文件
- reports 导出报表

数据库尚不存在时，脚本会给出提示并继续备份 uploads 和 reports。

## 测试

后端：

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

前端：

```powershell
cd frontend
npm run build
```

当前 pytest 使用独立测试库，不应污染本地使用数据库。

## 全功能自动化验收

命令：

```bat
scripts\full_auto_check.bat
```

说明：

该脚本会自动启动本地服务，运行后端 pytest 和前端 `npm run build`，然后通过后端 API 创建测试项目、导入测试 Excel、检查 Dashboard、预警、整改、报表、备份和诊断，并生成 `test_reports` 下的验收报告。

默认测试文件：

```text
sample_data\工程进度管理系统_全功能模拟测试表_v1.xlsx
```

如果未找到该文件，脚本会在报告中标记并提示将全功能模拟测试表放入 `sample_data` 目录。

## 常见问题

- 当前项目不存在或已被清理：请回到项目列表重新选择项目。
- 报表类型不存在或未注册：当前看板、Word 周报和整改清单已统一注册。
- 无法连接后端服务：运行 `scripts\dev_start.bat` 或 `scripts\start.bat`，并确认前端 API 地址指向实际后端端口。
- 导入校验失败：请检查字段映射、必填字段、日期格式和进度百分比。
- 报表导出失败：请确认存在已发布批次，且 reports 目录可写。
- 无已发布批次：请先完成确认导入并发布批次。
- 非进度 Sheet：请选择包含工程进度明细的 Sheet。
- 字段未映射：请在字段映射页补齐任务名称、专业、工程量、完成率等关键字段。
- 日期格式错误：请使用可识别的日期格式，或检查 Excel 单元格日期类型。
- 文件不存在：请确认上传文件或导出文件未被手动移动、删除。

## 相关文档

- DEPLOYMENT.md：本地部署和端口说明。
- BACKUP.md：备份与恢复说明。
- RELEASE_NOTES.md：版本能力、修复问题和正式版说明。










