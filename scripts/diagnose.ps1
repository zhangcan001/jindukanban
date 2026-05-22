param(
  [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [string]$BackendPort = $(if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8000" }),
  [string]$FrontendPort = $(if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" })
)

$ErrorActionPreference = "Stop"
$logDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "diagnose_$stamp.txt"

function Add-Line([string]$Text) {
  $lines.Add($Text)
  Write-Host $Text
}

function Test-Cmd([string]$Name) {
  try { (Get-Command $Name -ErrorAction Stop).Source } catch { "-" }
}

function Test-Port([int]$Port) {
  try {
    $c = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop | Select-Object -First 1
    if ($c) { return "占用 PID $($c.OwningProcess)" }
  } catch { }
  "未占用"
}

function Test-Url([string]$Url) {
  try {
    $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
    "可访问 HTTP $($r.StatusCode)"
  } catch {
    "不可访问"
  }
}

$lines = [System.Collections.Generic.List[string]]::new()
Add-Line "========================================"
Add-Line "工程进度看板 v5.0-desktop-shell 本地诊断"
Add-Line "========================================"
Add-Line ("诊断时间：" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Add-Line ("当前目录：" + $Root)
Add-Line ("Python：" + (Test-Cmd "python"))
Add-Line ("Node：" + (Test-Cmd "node"))
Add-Line ("npm：" + (Test-Cmd "npm"))
Add-Line ("backend 虚拟环境：" + (Test-Path (Join-Path $Root "backend\.venv\Scripts\python.exe")))
Add-Line ("frontend/dist：" + (Test-Path (Join-Path $Root "frontend\dist\index.html")))
Add-Line ("frontend_dist：" + (Test-Path (Join-Path $Root "frontend_dist\index.html")))
Add-Line ("后端端口 $BackendPort：" + (Test-Port ([int]$BackendPort)))
Add-Line ("前端端口 $FrontendPort：" + (Test-Port ([int]$FrontendPort)))

if (Test-Path (Join-Path $Root "frontend_dist\index.html")) {
  $db = Join-Path $Root "data\progress_dashboard.db"
  $uploads = Join-Path $Root "uploads"
  $exports = Join-Path $Root "exports"
} else {
  $db = Join-Path $Root "backend\progress_dashboard.db"
  $uploads = Join-Path $Root "backend\uploads"
  $exports = Join-Path $Root "backend\reports"
}
$backups = Join-Path $Root "backups"

Add-Line ("数据库文件：" + $db + " / " + (Test-Path $db))
Add-Line ("uploads 目录：" + $uploads + " / " + (Test-Path $uploads))
Add-Line ("exports 目录：" + $exports + " / " + (Test-Path $exports))
Add-Line ("backups 目录：" + $backups + " / " + (Test-Path $backups))

$latest = "-"
if (Test-Path $backups) {
  $b = Get-ChildItem $backups -Directory -Filter "backup_*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($b) { $latest = $b.LastWriteTime.ToString("yyyy-MM-dd HH:mm") }
}
Add-Line ("最近一次备份时间：" + $latest)
Add-Line ("后端 health：" + (Test-Url ("http://127.0.0.1:$BackendPort/api/health")))
Add-Line ("runtime-status：" + (Test-Url ("http://127.0.0.1:$BackendPort/api/maintenance/runtime-status")))

$lines | Set-Content -LiteralPath $logFile -Encoding UTF8
Write-Host ""
Write-Host ("诊断日志已生成：" + $logFile)








