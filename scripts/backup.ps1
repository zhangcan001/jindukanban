param(
  [Parameter(Mandatory = $true)]
  [string]$Root
)

$ErrorActionPreference = "Stop"
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$isPortable = Test-Path (Join-Path $rootPath "frontend_dist\index.html")
$backupRoot = Join-Path $rootPath "backups"

if ($isPortable) {
  foreach ($name in @("data", "uploads", "exports", "backups", "logs")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $rootPath $name) | Out-Null
  }
  $db = Join-Path $rootPath "data\progress_dashboard.db"
  $uploads = Join-Path $rootPath "uploads"
  $exports = Join-Path $rootPath "exports"
  $exportBackupName = "exports"
} else {
  $db = Join-Path $rootPath "backend\progress_dashboard.db"
  $uploads = Join-Path $rootPath "backend\uploads"
  $exports = Join-Path $rootPath "backend\reports"
  $exportBackupName = "reports"
}

New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$target = Join-Path $backupRoot "backup_$stamp"

Write-Host "========================================"
Write-Host "工程进度看板 v5.0-desktop-shell 本地备份"
Write-Host "========================================"
Write-Host "本次将备份："
Write-Host " - SQLite 数据库"
Write-Host " - uploads 上传文件"
Write-Host " - exports 或 reports 导出文件"
Write-Host "备份目录：$target"

New-Item -ItemType Directory -Force -Path $target | Out-Null

if (Test-Path $db) {
  $dbBackupPath = Join-Path $target (Split-Path $db -Leaf)
  $backupScript = Join-Path $rootPath "scripts\sqlite_backup.py"
  $pythonCmd = $null
  $venvPython = Join-Path $rootPath "backend\.venv\Scripts\python.exe"
  if (Test-Path $venvPython) { $pythonCmd = $venvPython }
  elseif (Get-Command python -ErrorAction SilentlyContinue) { $pythonCmd = "python" }
  elseif (Get-Command py -ErrorAction SilentlyContinue) { $pythonCmd = "py" }

  if ($pythonCmd -and (Test-Path $backupScript)) {
    Write-Host "[备份] 使用 SQLite 在线备份 API（无需停服）..."
    & $pythonCmd $backupScript $db $dbBackupPath
    if ($LASTEXITCODE -ne 0) {
      Write-Host "[错误] SQLite 在线备份失败，请检查数据库状态。"
      exit 1
    }
  } else {
    Write-Host "[警告] 未找到 Python 或备份脚本，回退到文件复制（可能不一致，请先停服）。"
    Copy-Item -LiteralPath $db -Destination $dbBackupPath -Force
  }
} else {
  Write-Host "[提示] 未找到数据库文件，可能尚未创建项目；本次继续备份目录。"
}

if (Test-Path $uploads) {
  Copy-Item -LiteralPath $uploads -Destination (Join-Path $target "uploads") -Recurse -Force
} else {
  Write-Host "[提示] 未找到 uploads 目录，跳过上传文件备份。"
}

if (Test-Path $exports) {
  Copy-Item -LiteralPath $exports -Destination (Join-Path $target $exportBackupName) -Recurse -Force
} else {
  Write-Host "[提示] 未找到导出目录，跳过导出文件备份。"
}

$info = @(
  "备份时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
  "项目版本：v5.0-desktop-shell",
  "数据库路径：$db",
  "上传目录：$uploads",
  "导出目录：$exports",
  "备份目录：$target"
)
$info | Set-Content -LiteralPath (Join-Path $target "backup_info.txt") -Encoding UTF8

Write-Host ""
Write-Host "备份完成：$target"
Write-Host "已生成：$(Join-Path $target 'backup_info.txt')"
Start-Process explorer.exe -ArgumentList $target








