param(
  [Parameter(Mandatory = $true)][string]$Target,
  [Parameter(Mandatory = $true)][string]$Version,
  [Parameter(Mandatory = $true)][string]$Root,
  [string]$PackageType = "installer-lite"
)

$ErrorActionPreference = "Stop"
$targetPath = (Resolve-Path -LiteralPath $Target).Path
$appPath = Join-Path $targetPath "app"

function Write-Launcher([string]$Name, [string]$ScriptName, [string]$ActionText) {
  $content = @(
    "@echo off",
    "setlocal EnableExtensions",
    "set ""APP_DIR=%~dp0app""",
    "if not exist ""%APP_DIR%\scripts\$ScriptName"" (",
    "  echo [错误] 未找到 app\scripts\$ScriptName，请确认安装包目录完整。",
    "  pause",
    "  exit /b 1",
    ")",
    "echo $ActionText",
    "call ""%APP_DIR%\scripts\$ScriptName"" %*",
    "if errorlevel 1 (",
    "  echo [错误] 操作失败，请查看 app\logs 或 app\.runtime 日志。",
    "  pause",
    "  exit /b 1",
    ")",
    "exit /b 0"
  )
  $content | Set-Content -LiteralPath (Join-Path $targetPath $Name) -Encoding Default
}

Write-Launcher "启动系统.bat" "start.bat" "正在启动工程进度管理系统..."
Write-Launcher "停止系统.bat" "stop.bat" "正在停止工程进度管理系统..."
Write-Launcher "重启系统.bat" "restart.bat" "正在重启工程进度管理系统..."
Write-Launcher "备份数据.bat" "backup.bat" "正在备份数据..."
Write-Launcher "诊断系统.bat" "diagnose.bat" "正在诊断系统..."
Write-Launcher "查看恢复说明.bat" "restore_guide.bat" "正在打开恢复说明..."

$shortcutLauncher = @(
  "@echo off",
  "setlocal EnableExtensions",
  "set ""ROOT=%~dp0""",
  "powershell -NoProfile -ExecutionPolicy Bypass -File ""%ROOT%app\scripts\create_installer_shortcut.ps1"" -Root ""%ROOT%""",
  "if errorlevel 1 (",
  "  echo [错误] 桌面快捷方式创建失败。",
  "  pause",
  "  exit /b 1",
  ")",
  "pause",
  "exit /b 0"
)
$shortcutLauncher | Set-Content -LiteralPath (Join-Path $targetPath "创建桌面快捷方式.bat") -Encoding Default

$shortcutScript = @'
param(
  [Parameter(Mandatory = $true)][string]$Root
)

$ErrorActionPreference = "Stop"
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$exeLauncher = Join-Path $rootPath "工程进度管理系统.exe"
$startBat = Join-Path $rootPath "启动系统.bat"
$targetPath = if (Test-Path -LiteralPath $exeLauncher) { $exeLauncher } else { $startBat }
$desktop = [Environment]::GetFolderPath("DesktopDirectory")
$shortcutPath = Join-Path $desktop "工程进度管理系统.lnk"

if (-not (Test-Path -LiteralPath $targetPath)) {
  throw "未找到 工程进度管理系统.exe 或 启动系统.bat。"
}

if (Test-Path -LiteralPath $shortcutPath) {
  $answer = Read-Host "桌面快捷方式已存在，是否覆盖？(Y/N)"
  if ($answer -notin @("Y", "y")) {
    Write-Host "已取消创建快捷方式。"
    exit 0
  }
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $rootPath
$icon = Join-Path $rootPath "app\icon.ico"
if (Test-Path -LiteralPath $icon) {
  $shortcut.IconLocation = $icon
} else {
  $shortcut.IconLocation = "$env:SystemRoot\System32\SHELL32.dll,167"
}
$shortcut.Description = "工程进度管理系统"
$shortcut.Save()
Write-Host "已创建桌面快捷方式：$shortcutPath"
'@
$shortcutScript | Set-Content -LiteralPath (Join-Path $appPath "scripts\create_installer_shortcut.ps1") -Encoding UTF8

$readme = @'
# 工程进度管理系统 __VERSION__ 本地安装使用说明

当前推荐版本：__VERSION__

核心能力：

- Dashboard V2 默认看板
- 总体 / 专业 / 楼栋三视图
- 权重归一化统计
- full_auto_check 全功能自动验收
- 安装包本地运行
- 备份 / 恢复 / 诊断

## 第一次使用

1. 解压或复制整个 `工程进度管理系统-__VERSION__` 文件夹。
2. 优先双击 `工程进度管理系统.exe`；也可双击 `启动系统.bat`。
3. 系统界面打开后，可创建示例项目并导入 `app\sample_data` 中的示例 Excel。
4. 正式使用前建议先双击 `备份数据.bat` 做一次备份。

## EXE 启动方式

1. 双击 `工程进度管理系统.exe`。
2. 等待系统自动启动。
3. 系统界面会自动打开。
4. 不要删除 `app\data`、`app\uploads`、`app\exports`、`app\backups`。
5. 迁移到其他电脑时，复制整个文件夹。

## 桌面窗口启动方式

1. 双击 `工程进度管理系统.exe`。
2. 系统会自动启动本地服务。
3. 稍等片刻后进入独立软件窗口。
4. 不需要手动打开浏览器。
5. 数据保存在 `app\data`、`app\uploads`、`app\exports`、`app\backups`。
6. 迁移到其他电脑时复制整个文件夹。

## 如何启动系统

如果根目录存在 `工程进度管理系统.exe`，推荐双击该 EXE 启动。EXE 会自动启动本地服务，并打开系统界面。

双击根目录 `启动系统.bat` 也可以启动系统。系统会使用 `app` 目录内的后端、前端构建产物和本地数据目录。

## 如何停止系统

双击根目录 `停止系统.bat`。

## 如何创建桌面快捷方式

双击 `创建桌面快捷方式.bat`。快捷方式名称为“工程进度管理系统”，优先指向本文件夹中的 `工程进度管理系统.exe`；如果 EXE 不存在，则 fallback 到 `启动系统.bat`。重复创建时会提示是否覆盖。

## 如何导入示例数据

1. 启动系统。
2. 创建示例项目。
3. 进入导入页，选择 `app\sample_data` 中的 Excel。
4. 推荐先导入 `01_单Sheet标准进度表.xlsx`，再体验 `02_多Sheet进度表.xlsx`。

## 数据保存在哪里

- 数据库：`app\data\progress_dashboard.db`
- 上传文件：`app\uploads`
- 导出报表：`app\exports`
- 备份：`app\backups`
- 日志：`app\logs` 和 `app\.runtime`

## 如何备份

双击 `备份数据.bat`。备份会写入 `app\backups`。

## 如何恢复

双击 `查看恢复说明.bat` 查看步骤。恢复前请先停止系统，并再次备份当前数据。

## 如何迁移到另一台电脑

先停止系统，再复制整个 `工程进度管理系统-__VERSION__` 文件夹到新电脑。数据保存在本文件夹内，不需要服务器。

## 常见问题

- 启动失败：运行 `诊断系统.bat`。
- 端口占用：先运行 `停止系统.bat`，或关闭占用 8000 端口的程序。
- 不要手动删除 `app\data`、`app\backups`、`app\uploads`、`app\exports`。
- 在 `/about` 页面确认运行模式为 `desktop-shell`、`exe-launcher` 或 `installer-lite`，并确认数据目录位于 `app\data`。

### 双击 exe 没反应怎么办？

- 运行 `诊断系统.bat`。
- 查看 `app\logs` 和 `app\.runtime`。
- 检查端口是否被占用。

### 杀毒软件提示怎么办？

- 本程序为本地启动器，可能因未签名被提示。
- 可改用 `启动系统.bat`。

### 数据在哪里？

- `app\data`
- `app\uploads`
- `app\exports`
- `app\backups`

## 如果启动后空白

1. 先关闭软件。
2. 运行 `诊断系统.bat`。
3. 检查 `app\logs\desktop_launcher.log`。
4. 如果杀毒软件拦截，请允许本程序运行。
5. 如仍失败，可临时运行 `启动系统.bat` 并访问本地地址排查。
'@
$readme = $readme.Replace("__VERSION__", $Version)
$readme | Set-Content -LiteralPath (Join-Path $targetPath "README_本地安装使用说明.md") -Encoding UTF8

$pythonVersion = (python --version 2>&1) -join " "
$nodeVersion = (node --version 2>&1) -join " "
$packageTypeLabel = if ($PackageType -eq "desktop-shell") { "Windows 独立桌面窗口版" } elseif ($PackageType -eq "exe-launcher") { "Windows 可移植 EXE 启动包" } else { "Windows 本地轻量安装包" }
$startMode = if ($PackageType -in @("exe-launcher", "desktop-shell")) { "双击 工程进度管理系统.exe" } else { "双击 启动系统.bat" }
$runMode = if ($PackageType -eq "desktop-shell") { "desktop-shell" } elseif ($PackageType -eq "exe-launcher") { "exe-launcher" } else { "installer-lite" }
$info = @(
  "版本：$Version",
  "当前推荐版本：$Version",
  "生成时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
  "包类型：$packageTypeLabel",
  "启动方式：$startMode",
  "运行模式：$runMode",
  "说明：本版本不再依赖外部浏览器作为主界面，系统将在独立桌面窗口中运行。",
  "Python 版本：$pythonVersion",
  "Node 版本：$nodeVersion",
  "是否包含示例数据：是",
  "是否包含 PDF 导出：是",
  "是否包含 AI 辅助：是",
  "是否包含备份恢复：是",
  "Dashboard V2：已启用",
  "Dashboard V2 默认看板：是",
  "full_auto_check：已支持",
  "full_auto_check 全功能自动验收：是",
  "数据目录：app\data",
  "上传目录：app\uploads",
  "导出目录：app\exports",
  "备份目录：app\backups"
)
$info | Set-Content -LiteralPath (Join-Path $targetPath "package_info.txt") -Encoding UTF8

if ($PackageType -eq "desktop-shell") {
  New-Item -ItemType File -Force -Path (Join-Path $appPath "DESKTOP_SHELL") | Out-Null
} elseif ($PackageType -eq "exe-launcher") {
  New-Item -ItemType File -Force -Path (Join-Path $appPath "EXE_LAUNCHER") | Out-Null
} else {
  New-Item -ItemType File -Force -Path (Join-Path $appPath "INSTALLER_LITE") | Out-Null
}
