# v3.4-final-stabilization 备份与恢复说明

当前版本 v3.4-final-stabilization 面向本地单机长期使用，默认数据库为 SQLite。升级、清理测试数据、移动目录或连续试用前，建议先备份。

本文已完成 v3.4-final-stabilization 文档一致性整理，当前内容适用于本地单机与 portable 最小回归。

v3.4-final-stabilization 同时支持源码目录和 portable 发布包。portable 包内默认使用：

```text
data/progress_dashboard.db
uploads/
exports/
backups/
logs/
```

## 1. 一键备份

在项目根目录运行：

```bat
scripts\backup.bat
```

脚本会创建：

```text
backups\backup_YYYYMMDD_HHMMSS\
```

备份内容：

- `progress_dashboard.db` SQLite 数据库文件。
- `uploads` 上传文件目录。
- `reports` 导出报表目录，也就是当前本地 exports 目录。
- `backup_info.txt` 备份说明文件。

多 Sheet 批量导入的 `import_group_id`、`sheet_name`、计划基线绑定和每个 Sheet 独立批次都保存在 SQLite 数据库中，随数据库一起备份和恢复。

项目归档状态、批次冻结状态、维护日志、安全清理记录和报表导出记录也保存在 SQLite 数据库中，随数据库一起备份和恢复。v3.4-final-stabilization 已统一整改跟踪表等导出结果的历史记录口径。备份记录页只做完整性检查和恢复说明展示，不会自动恢复或覆盖当前数据。

脚本优先备份 `backend` 下的目录；如检测到旧版根目录 `uploads` 或 `reports`，会自动兼容。
在 portable 包中运行根目录 `backup.bat` 时，脚本会备份 portable 包内部的 `data`、`uploads`、`exports` 到当前包内的 `backups`，不会使用源码目录数据库。

## 2. backup_info.txt

每次备份都会生成：

```text
backup_info.txt
```

其中记录：

- 备份时间
- 项目版本
- 数据库路径
- 上传目录
- 导出目录
- 备份目录

## 3. 数据库不存在时

如果尚未启动后端、尚未创建项目，或数据库被移走，脚本会提示未找到数据库文件，并继续备份 uploads 和 reports，不会直接用错误信息中断。

## 4. 手动备份

最小备份集：

```text
backend/progress_dashboard.db
backend/uploads/
```

portable 包最小备份集：

```text
data/progress_dashboard.db
uploads/
exports/
```

建议同时备份：

```text
backend/reports/
```

PowerShell 示例：

```powershell
New-Item -ItemType Directory backups\manual_20260515
Copy-Item backend\progress_dashboard.db backups\manual_20260515\
Copy-Item backend\uploads backups\manual_20260515\uploads -Recurse
Copy-Item backend\reports backups\manual_20260515\reports -Recurse
```

## 5. 恢复前必须确认

恢复操作会覆盖当前数据。恢复前必须：

1. 运行 `scripts\stop.bat` 停止本项目服务。
2. 运行 `scripts\backup.bat` 备份当前数据。
3. 确认目标备份目录正确，不要覆盖到错误目录。

## 6. 恢复步骤

也可以运行以下脚本查看恢复说明：

```bat
scripts\restore_guide.bat
```

手动恢复步骤：

1. 运行 `scripts\stop.bat` 停止本项目服务。
2. 运行 `scripts\backup.bat` 备份当前数据库、上传文件和导出报表。
3. 从目标备份目录中找到 `progress_dashboard.db`。
4. 用备份的数据库文件替换当前 `backend\progress_dashboard.db`。
5. 用备份中的 `uploads` 替换当前 `backend\uploads`。
6. 如需恢复导出文件，用备份中的 `reports` 替换当前 `backend\reports`。
7. 运行 `scripts\start.bat` 启动服务。
8. 打开工作台，检查项目、导入批次、进度明细、报表历史和已导出文件。

portable 包恢复时，对应替换：

```text
data/progress_dashboard.db
uploads/
exports/
```

## 7. 注意事项

- 不要在后端运行中直接替换数据库文件。
- 不要把备份恢复到错误项目目录。
- 备份目录建议保留日期时间，不要手动改成相同名称覆盖旧备份。
- 长期试用期间建议每天结束前备份一次。
- 清理测试项目和未发布批次前建议先备份。
- 取消冻结、正式执行安全清理或恢复备份前，建议先运行一次 `scripts\backup.bat`。
- portable 包默认使用后端端口 `8000`、前端端口 `5173`。端口被占用时，先停止本项目；如果仍被占用，请关闭占用程序或用临时端口启动，避免误杀其他程序。





