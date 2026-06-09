param(
  [Parameter(Mandatory = $true)][string]$Root,
  [Parameter(Mandatory = $true)][string]$Version,
  [string]$PackageType = "installer-lite"
)

$ErrorActionPreference = "Stop"
$rootPath = (Resolve-Path -LiteralPath $Root).Path
$releaseRoot = Join-Path $rootPath "release"
$target = Join-Path $releaseRoot "工程进度管理系统-$Version"
$app = Join-Path $target "app"
$frontendDist = Join-Path $rootPath "frontend\dist"

function Invoke-Robocopy([string]$Source, [string]$Dest, [string[]]$Options) {
  New-Item -ItemType Directory -Force -Path $Dest | Out-Null
  & robocopy $Source $Dest @Options | Out-Null
  $code = $LASTEXITCODE
  if ($code -ge 8) {
    throw "robocopy failed with exit code $code for $Source -> $Dest"
  }
}

function Clear-ReleaseCache([string]$Path) {
  Get-ChildItem -LiteralPath $Path -Recurse -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in @("__pycache__", ".pytest_cache") } |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "\.(pyc|pyo|log)$" -or $_.Name -match "\.(out|err)\.log$" } |
    Remove-Item -Force -ErrorAction SilentlyContinue
}

if (Test-Path -LiteralPath $target) {
  Remove-Item -LiteralPath $target -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $app | Out-Null
foreach ($dir in @("frontend_dist", "scripts", "data", "uploads", "exports", "backups", "logs")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $app $dir) | Out-Null
}

Invoke-Robocopy (Join-Path $rootPath "backend") (Join-Path $app "backend") @("/E", "/XD", "__pycache__", ".pytest_cache", "uploads", "reports", "/XF", "*.pyc", "*.pyo", "progress_dashboard.db", "progress_dashboard.db-*", "test_progress_dashboard.db", "test_progress_dashboard.db-*", "*.log", "*.out.log", "*.err.log")
if (-not (Test-Path -LiteralPath (Join-Path $app "backend\app\main.py"))) {
  Copy-Item -LiteralPath (Join-Path $rootPath "backend\app") -Destination (Join-Path $app "backend\app") -Recurse -Force
}
if (Test-Path -LiteralPath (Join-Path $rootPath "backend\.venv")) {
  $targetVenv = Join-Path $app "backend\.venv"
  if (Test-Path -LiteralPath $targetVenv) {
    Remove-Item -LiteralPath $targetVenv -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path $targetVenv | Out-Null
  Get-ChildItem -LiteralPath (Join-Path $rootPath "backend\.venv") -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $targetVenv -Recurse -Force
  }
}
foreach ($item in @("progress_dashboard.db", "progress_dashboard.db-*", "test_progress_dashboard.db", "test_progress_dashboard.db-*", "uvicorn*.log", "uvicorn*.out.log", "uvicorn*.err.log")) {
  Get-ChildItem -LiteralPath (Join-Path $app "backend") -Filter $item -File -ErrorAction SilentlyContinue | Remove-Item -Force
}
foreach ($dir in @("__pycache__", ".pytest_cache", "uploads", "reports", "backups")) {
  $path = Join-Path (Join-Path $app "backend") $dir
  if (Test-Path -LiteralPath $path) {
    Remove-Item -LiteralPath $path -Recurse -Force
  }
}
Invoke-Robocopy $frontendDist (Join-Path $app "frontend_dist") @("/E")
$frontendAssets = Join-Path $app "frontend_dist\assets"
if (-not (Test-Path -LiteralPath $frontendAssets)) {
  throw "frontend assets missing after package assembly: $frontendAssets"
}
$frontendAssetCount = (Get-ChildItem -LiteralPath $frontendAssets -File -Force -ErrorAction SilentlyContinue | Measure-Object).Count
if ($frontendAssetCount -lt 1) {
  throw "frontend assets are empty after package assembly: $frontendAssets"
}
Invoke-Robocopy (Join-Path $rootPath "scripts") (Join-Path $app "scripts") @("/E", "/XF", "*.pyc", "*.pyo", "*.log", "*.out.log", "*.err.log")
Invoke-Robocopy (Join-Path $rootPath "sample_data") (Join-Path $app "sample_data") @("/E")

Copy-Item -LiteralPath (Join-Path $rootPath "README.md") -Destination (Join-Path $target "README_本地安装使用说明.md") -Force

@(
  "APP_NAME=progress-dashboard",
  "APP_ENV=production",
  "DATABASE_URL=sqlite:///../data/progress_dashboard.db",
  "UPLOAD_DIR=../uploads",
  "EXPORT_DIR=../exports",
  "BACKUP_DIR=../backups",
  "MAX_UPLOAD_SIZE_MB=20",
  "BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173",
  "LOG_LEVEL=INFO"
) | Set-Content -LiteralPath (Join-Path $app "backend\.env") -Encoding ASCII

& "$rootPath\scripts\write_installer_lite_files.ps1" -Target $target -Version $Version -Root $rootPath -PackageType $PackageType
Clear-ReleaseCache $target

Write-Host ""
if ($PackageType -eq "desktop-shell") {
  Write-Host "Desktop-shell package generated:"
} elseif ($PackageType -eq "exe-launcher") {
  Write-Host "EXE launcher package generated:"
} else {
  Write-Host "Installer-lite package generated:"
}
Write-Host $target
