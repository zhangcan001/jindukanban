$ErrorActionPreference = "Continue"

$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$runtimeDir = Join-Path $root ".runtime"
$detected = $false
$failed = $false

Write-Host "========================================"
Write-Host "工程进度看板 v5.0-desktop-shell 停止服务"
Write-Host "========================================"

function Stop-RecordedPid {
  param(
    [string]$PidFile,
    [string]$ServiceName
  )

  if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host "[$ServiceName] 未找到本项目 PID 记录。"
    return
  }

  $targetPid = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
  if (-not $targetPid) {
    Write-Host "[$ServiceName] PID 记录为空，已清理。"
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    return
  }

  $process = Get-Process -Id ([int]$targetPid) -ErrorAction SilentlyContinue
  if (-not $process) {
    Write-Host "[$ServiceName] 进程 $targetPid 已不存在，已清理 PID 文件。"
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    return
  }

  $script:detected = $true
  Write-Host "[$ServiceName] 正在停止本项目进程 $targetPid"
  try {
    Stop-Process -Id ([int]$targetPid) -Force -ErrorAction Stop
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
  } catch {
    Write-Host "[$ServiceName] 停止失败，请手动检查进程 $targetPid。"
    $script:failed = $true
  }
}

function Stop-ProjectPort {
  param(
    [int]$Port,
    [string]$ServiceName
  )

  $connections = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  foreach ($connection in $connections) {
    $process = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $connection.OwningProcess) -ErrorAction SilentlyContinue
    if (-not $process -or $process.CommandLine -notlike ("*" + $root + "*")) {
      Write-Host "[$ServiceName] 端口 $Port 被非本项目进程 $($connection.OwningProcess) 占用，已跳过。"
      continue
    }

    $script:detected = $true
    Write-Host "[$ServiceName] 正在停止本项目监听进程 $($connection.OwningProcess)"
    try {
      Stop-Process -Id ([int]$connection.OwningProcess) -Force -ErrorAction Stop
    } catch {
      Write-Host "[$ServiceName] 停止监听进程失败，请手动检查进程 $($connection.OwningProcess)。"
      $script:failed = $true
    }
  }
}

Stop-RecordedPid -PidFile (Join-Path $runtimeDir "backend.pid") -ServiceName "backend"
Stop-RecordedPid -PidFile (Join-Path $runtimeDir "frontend.pid") -ServiceName "frontend"
Stop-ProjectPort -Port 8000 -ServiceName "backend"
Stop-ProjectPort -Port 5173 -ServiceName "frontend"

if (-not $detected) {
  Write-Host "当前未检测到本项目服务。"
} elseif ($failed) {
  Write-Host "[警告] 部分服务停止失败，请根据上方 PID 手动检查。"
  exit 1
} else {
  Write-Host "系统已停止。"
}








