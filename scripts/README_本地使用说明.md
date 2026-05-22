# 工程进度看板本地使用说明

当前推荐版本：v4.9-exe-launcher

定位：本地单机便携版工程进度管理系统。

核心能力：

- Dashboard V2 默认看板
- 总体 / 专业 / 楼栋三视图
- 权重归一化统计
- full_auto_check 全功能自动验收
- 安装包本地运行
- 备份 / 恢复 / 诊断

## 第一次使用步骤

1. 双击 `diagnose.bat`，确认 Python、后端虚拟环境、端口和目录状态。
2. 双击 `create_shortcut.bat`，按提示创建桌面快捷方式。
3. 双击 `start.bat` 或桌面快捷方式启动系统。
4. 浏览器打开后进入“项目管理”，新建或选择项目；首次体验可点击“创建示例项目”。
5. 使用 `sample_data` 目录中的示例 Excel 体验单 Sheet 和多 Sheet 导入。

## 如何创建桌面快捷方式

双击 portable 包根目录的 `create_shortcut.bat`。

脚本会在当前用户桌面创建快捷方式：

```text
工程进度管理系统
```

如果快捷方式已存在，脚本会询问是否覆盖。

## 启动

双击 `start.bat`，浏览器会打开：

```text
http://127.0.0.1:5173
```

## 停止

双击 `stop.bat`。

## 重启

双击 `restart.bat`。

## 备份

双击 `backup.bat`，备份会写入 `backups` 目录。

建议在导入大批量数据、恢复备份、迁移电脑前都先执行一次备份。

## 诊断

双击 `diagnose.bat`，诊断日志会写入 `logs` 目录。

## 恢复备份

双击 `restore_guide.bat` 查看恢复步骤。恢复前请先停止系统，并再次执行备份。

## 数据目录

- 数据库：`data/progress_dashboard.db`
- 上传文件：`uploads/`
- 导出报表：`exports/`
- 备份：`backups/`
- 日志：`logs/`

## 迁移到另一台电脑

1. 先运行 `stop.bat` 停止系统。
2. 运行 `backup.bat` 备份当前数据。
3. 复制整个 `progress-dashboard-v4.9-exe-launcher` 文件夹到新电脑。
4. 在新电脑运行 `diagnose.bat`。
5. 再运行 `create_shortcut.bat` 和 `start.bat`。

## 内置页面

- 版本信息：`http://127.0.0.1:5173/about`
- 帮助中心：`http://127.0.0.1:5173/help`
- 新手引导：`http://127.0.0.1:5173/getting-started`
- 系统维护：`http://127.0.0.1:5173/maintenance`

## 当前限制

- 暂不提供安装程序。
- 暂不打包 Python 运行时。
- 暂不打包 Node 运行时。
- 暂不支持多用户。
- 暂不支持 PostgreSQL。
- 暂不支持 Docker。
- 暂不新增业务模块。
- 暂不扩展 AI 功能。
- 暂不支持云同步。
- 暂不支持移动端 App。
- 当前主要面向 Windows 本地单机使用。

## 常见问题

- 端口被占用：先运行 `stop.bat`；如果仍占用，请手动关闭旧服务。
- Python 不可用：安装 Python 3.12+，并确认 Python 在 PATH 中。
- Node 不可用：便携版运行不依赖 Node，只有重新构建前端时需要。
- 后端启动失败：检查 `backend\.venv` 和 `backend\.env`。
- `frontend_dist` 不存在：回源码目录运行 `npm run build` 后重新构建发布包。
- 数据库不存在：首次启动会自动创建 `data/progress_dashboard.db`。
- 报表导出失败：检查 `exports` 目录是否可写。
- 端口被占用：默认后端端口 `8000`、前端端口 `5173`。脚本不会自动关闭非本项目进程；请手动关闭占用程序，或在命令行中设置临时端口后运行 `start.bat`：

```bat
set BACKEND_PORT=8028
set FRONTEND_PORT=5228
start.bat
```
- 浏览器打不开：手动访问 `http://127.0.0.1:5173`。






