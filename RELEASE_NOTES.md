# RELEASE_NOTES

## v4.9-exe-launcher

### 版本性质

Windows 可移植 EXE 启动包版本，不新增业务功能。

### 完成内容

- 新增 `工程进度管理系统.exe` 启动器，采用“文件夹 + EXE 启动器”交付方式。
- 新增 `scripts\build_exe_launcher.bat` 和 `scripts\build_exe_package.bat`。
- EXE 启动器自动定位包根目录和 `app` 目录，启动后端、前端并打开浏览器。
- EXE 包继续使用包内 `app\data`、`app\uploads`、`app\exports`、`app\backups` 保存本地数据。
- 桌面快捷方式优先指向 `工程进度管理系统.exe`，EXE 不存在时 fallback 到 `启动系统.bat`。
- 保留 `启动系统.bat`、`停止系统.bat`、`备份数据.bat`、`诊断系统.bat` 等维护入口。
- 保持 Excel 导入逻辑、字段识别逻辑、进度计算公式、Dashboard V2 统计逻辑、报表导出逻辑和 AI 能力不变。

### 验收范围

- `scripts\quick_check.bat`
- `scripts\full_auto_check.bat`
- `scripts\build_exe_package.bat`
- release 包内 EXE 启动、full_auto_check、备份、诊断、停止

### 当前推荐版本

- `v4.9-exe-launcher`

## v4.8.4-final-package-refresh

### 版本性质

最终交付包重建复验版本，不新增业务功能。

### 完成内容

- 统一版本号为 `v4.8.4-final-package-refresh`。
- 重建 installer-lite / portable 交付包。
- 确认 v4.8.3 Dashboard V2 楼层点击不污染全局筛选状态的修复进入交付包。
- 保持导入逻辑、字段识别逻辑、进度计算公式和 Dashboard V2 统计逻辑不变。

## T039 安装包重建与交付检查

### 完成内容

- 重建 installer-lite / portable 交付包
- 默认入口保持 Dashboard V2
- 自动验收脚本与测试样本随包交付
- 补充本地安装说明、版本说明和交付检查结果

### 核心能力

- Dashboard V2 默认看板
- 总体 / 专业 / 楼栋三视图
- 权重归一化统计
- full_auto_check 全功能自动验收
- 安装包本地运行
- 备份 / 恢复 / 诊断

## T037 Dashboard V2 默认化

### 完成内容

- 新版看板设为默认入口
- 旧版看板保留为兼容入口
- 工作台 / 导入完成 / 报表中心等入口统一跳转新版看板
- 旧版看板增加兼容提示

## v3.9-demo-onboarding

### 优化内容

- 新增 `sample_data` 示例 Excel 和示例数据说明。
- 新增示例项目入口，并自动创建默认计划基线。
- 新增 `/getting-started` 新手引导页。
- 优化无项目首页，提供创建项目、创建示例项目、新手引导和导入入口。
- 帮助中心补充示例数据、字段说明、单 Sheet、多 Sheet、计划基线、预警整改、报表和备份说明。
- portable 包集成示例数据并更新 package_info。

### 当前限制

- 不改 Excel 导入核心逻辑。
- 不改字段识别核心逻辑。
- 不改进度计算公式。
- 不改报表导出核心逻辑。
- 不扩展 AI。
- 不做权限、PostgreSQL、Docker。
