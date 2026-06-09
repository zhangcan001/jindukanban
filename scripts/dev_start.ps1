$ErrorActionPreference = "Continue"

$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$backendDir = Join-Path $root "backend"
$frontendDir = Join-Path $root "frontend"
$runtimeDir = Join-Path $root ".runtime"
$backendPort = if ($env:BACKEND_PORT) { [int]$env:BACKEND_PORT } else { 8000 }
$frontendPort = if ($env:FRONTEND_PORT) { [int]$env:FRONTEND_PORT } else { 5173 }
$portFallbackAttempts = 10
$pythonExe = Join-Path $backendDir ".venv\Scripts\python.exe"
$viteCmd = Join-Path $frontendDir "node_modules\.bin\vite.cmd"

Write-Host "========================================"
Write-Host "工程进度看板开发启动"
Write-Host "Backend default port $backendPort, frontend default port $frontendPort"
Write-Host "========================================"

function Test-UrlReady {
  param(
    [string]$Url,
    [switch]$AllowClientError
  )

  try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
    if ($AllowClientError) {
      return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    }
    return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300)
  } catch {
    return $false
  }
}

function Wait-UrlReady {
  param(
    [string]$Url,
    [string]$Name,
    [int]$TimeoutSeconds = 30,
    [switch]$AllowClientError
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-UrlReady -Url $Url -AllowClientError:$AllowClientError) {
      return $true
    }
    Start-Sleep -Milliseconds 250
  }

  Write-Host "[错误] $Name 超时：$Url"
  return $false
}

function Get-PortStatus {
  param(
    [int]$Port,
    [string[]]$Needles
  )

  $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $connection) {
    return "free"
  }

  $process = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $connection.OwningProcess) -ErrorAction SilentlyContinue
  $commandLine = if ($process) { [string]$process.CommandLine } else { "" }
  $normalizedCommand = $commandLine.ToLowerInvariant()
  $normalizedRoot = $root.ToLowerInvariant()
  $isProject = $normalizedCommand.Contains($normalizedRoot)
  foreach ($needle in $Needles) {
    if (-not $normalizedCommand.Contains($needle.ToLowerInvariant())) {
      $isProject = $false
      break
    }
  }

  if ($isProject) {
    return "project"
  }
  return "other"
}

function Find-AvailablePort {
  param(
    [int]$StartPort,
    [string[]]$Needles,
    [int]$MaxAttempts = 10,
    [string]$ServiceLabel = "service"
  )

  for ($offset = 0; $offset -lt $MaxAttempts; $offset++) {
    $candidate = $StartPort + $offset
    $status = Get-PortStatus -Port $candidate -Needles $Needles
    if ($status -eq "free" -or $status -eq "project") {
      if ($offset -gt 0) {
        Write-Host "[提示] $ServiceLabel 默认端口 $StartPort 被其他程序占用，自动切换到 $candidate。"
      }
      return @{ Port = $candidate; Status = $status }
    }
  }
  Write-Host "[错误] $ServiceLabel 在 $StartPort .. $($StartPort + $MaxAttempts - 1) 范围内未找到可用端口。"
  return $null
}

function Write-ListeningPid {
  param(
    [int]$Port,
    [string]$PidFile,
    [string]$ServiceName
  )

  for ($i = 0; $i -lt 10; $i++) {
    $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($connection) {
      Set-Content -LiteralPath $PidFile -Value $connection.OwningProcess
      return
    }
    Start-Sleep -Milliseconds 100
  }

  Write-Host "[警告] 未能识别$ServiceName实际监听 PID，停止脚本可能需要手动处理。"
}

function Open-UrlDetached {
  param([string]$Url)

  try {
    Start-Process -FilePath $Url | Out-Null
  } catch {
    Write-Host "[警告] 自动打开浏览器失败，请手动访问：$Url"
  }
}

function Try-ReuseRuntimeState {
  $portsFile = Join-Path $runtimeDir "ports.json"
  if (-not (Test-Path -LiteralPath $portsFile)) {
    return $false
  }

  try {
    $state = Get-Content -LiteralPath $portsFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    $stateBackendPort = [int]$state.backend_port
    $stateFrontendPort = if ($state.frontend_port) { [int]$state.frontend_port } else { 0 }
    $stateBackendUrl = if ($state.backend_url) { [string]$state.backend_url } else { "http://127.0.0.1:$stateBackendPort" }
    $stateFrontendUrl = if ($state.primary_url) { [string]$state.primary_url } elseif ($stateFrontendPort -gt 0) { "http://127.0.0.1:$stateFrontendPort/" } else { "$stateBackendUrl/" }
  } catch {
    return $false
  }

  if ($stateBackendPort -le 0 -or -not (Test-UrlReady -Url "$stateBackendUrl/api/health")) {
    return $false
  }
  if (-not (Test-UrlReady -Url $stateFrontendUrl -AllowClientError)) {
    return $false
  }

  Write-Host "系统已运行，直接打开。"
  Open-UrlDetached $stateFrontendUrl
  return $true
}

if (Try-ReuseRuntimeState) {
  exit 0
}

if (-not (Test-Path -LiteralPath (Join-Path $backendDir "app\main.py"))) {
  Write-Host "[错误] 当前目录不是项目根目录，未找到 backend\app\main.py。"
  exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendDir "package.json"))) {
  Write-Host "[错误] 未找到 frontend\package.json。"
  exit 1
}
if (-not (Test-Path -LiteralPath $runtimeDir)) {
  New-Item -ItemType Directory -Path $runtimeDir | Out-Null
}
if (-not (Test-Path -LiteralPath $pythonExe)) {
  Write-Host "[错误] 后端虚拟环境不存在：$backendDir\.venv"
  Write-Host "       请先创建虚拟环境并安装 backend\requirements.txt。"
  exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host "[错误] 未找到 node，请先安装 Node.js 或确认 node 在 PATH 中。"
  exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $frontendDir "node_modules"))) {
  Write-Host "[错误] 前端依赖不存在：$frontendDir\node_modules"
  Write-Host "       请先在 frontend 目录执行 npm install。"
  exit 1
}
if (-not (Test-Path -LiteralPath $viteCmd)) {
  Write-Host "[错误] 未找到 Vite 启动脚本：$viteCmd"
  Write-Host "       请先在 frontend 目录执行 npm install。"
  exit 1
}

$backendPick = Find-AvailablePort -StartPort $backendPort -Needles @("uvicorn", "app.main:app") -MaxAttempts $portFallbackAttempts -ServiceLabel "后端"
if (-not $backendPick) {
  exit 1
}
$backendPort = [int]$backendPick.Port
$backendUrl = "http://127.0.0.1:$backendPort"
$healthUrl = "$backendUrl/api/health"

if (Test-UrlReady -Url $healthUrl) {
  Write-Host "后端已运行，跳过启动。"
} else {
  $backendPortStatus = $backendPick.Status
  if ($backendPortStatus -eq "project") {
    Write-Host "后端端口 $backendPort 已被本项目后端占用，等待健康检查。"
    if (-not (Wait-UrlReady -Url $healthUrl -Name "后端健康检查")) {
      Write-Host "[错误] 本项目后端进程已占用端口，但健康检查未通过：$healthUrl"
      Write-Host "       请查看 .runtime\backend.err.log 或运行 scripts\stop.bat 后重试。"
      exit 1
    }
    Write-Host "后端已运行，跳过启动。"
  } else {
    Write-Host "正在启动后端..."
    $backendOut = Join-Path $runtimeDir "backend.out.log"
    $backendErr = Join-Path $runtimeDir "backend.err.log"
    try {
      $backendProcess = Start-Process -FilePath $pythonExe -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$backendPort") -WorkingDirectory $backendDir -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru -WindowStyle Hidden
      Set-Content -LiteralPath (Join-Path $runtimeDir "backend.pid") -Value $backendProcess.Id
    } catch {
      Write-Host "[错误] 后端启动命令执行失败。"
      exit 1
    }

    if (-not (Wait-UrlReady -Url $healthUrl -Name "后端健康检查")) {
      Write-Host "[错误] 后端健康检查未通过，请查看日志："
      Write-Host "       $backendErr"
      exit 1
    }
    Write-ListeningPid -Port $backendPort -PidFile (Join-Path $runtimeDir "backend.pid") -ServiceName "后端"
    Write-Host "后端健康检查通过。"
  }
}

$frontendPick = Find-AvailablePort -StartPort $frontendPort -Needles @("vite") -MaxAttempts $portFallbackAttempts -ServiceLabel "前端"
if (-not $frontendPick) {
  exit 1
}
$frontendPort = [int]$frontendPick.Port
$frontendUrl = "http://127.0.0.1:$frontendPort"

if (Test-UrlReady -Url "$frontendUrl/" -AllowClientError) {
  Write-Host "前端已运行，跳过启动。"
  & (Join-Path $PSScriptRoot "write_runtime_state.ps1") -RuntimeDir $runtimeDir -BackendPort $backendPort -FrontendPort $frontendPort -PrimaryUrl "$frontendUrl/" -Mode "source"
  Open-UrlDetached $frontendUrl
  exit 0
}

$frontendPortStatus = $frontendPick.Status
if ($frontendPortStatus -eq "project") {
  Write-Host "前端端口 $frontendPort 已被本项目进程占用，等待端口就绪。"
  if (-not (Wait-UrlReady -Url "$frontendUrl/" -Name "前端端口检查" -AllowClientError)) {
    Write-Host "[错误] 本项目前端进程已占用端口，但页面未就绪。"
    exit 1
  }
  Write-Host "前端已运行，跳过启动。"
  & (Join-Path $PSScriptRoot "write_runtime_state.ps1") -RuntimeDir $runtimeDir -BackendPort $backendPort -FrontendPort $frontendPort -PrimaryUrl "$frontendUrl/" -Mode "source"
  Open-UrlDetached $frontendUrl
  exit 0
}

Write-Host "正在启动前端..."
$frontendOut = Join-Path $runtimeDir "frontend.out.log"
$frontendErr = Join-Path $runtimeDir "frontend.err.log"
$env:VITE_API_BASE_URL = $backendUrl
try {
  $frontendProcess = Start-Process -FilePath $viteCmd -ArgumentList @("--host", "127.0.0.1", "--port", "$frontendPort") -WorkingDirectory $frontendDir -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru -WindowStyle Hidden
  Set-Content -LiteralPath (Join-Path $runtimeDir "frontend.pid") -Value $frontendProcess.Id
} catch {
  Write-Host "[错误] 前端启动命令执行失败。"
  exit 1
}

if (-not (Wait-UrlReady -Url "$frontendUrl/" -Name "前端端口检查" -AllowClientError)) {
  Write-Host "[错误] 前端端口未就绪，请查看日志："
  Write-Host "       $frontendErr"
  exit 1
}
Write-ListeningPid -Port $frontendPort -PidFile (Join-Path $runtimeDir "frontend.pid") -ServiceName "前端"

Write-Host "系统已启动。"
Write-Host "访问地址：$frontendUrl"
& (Join-Path $PSScriptRoot "write_runtime_state.ps1") -RuntimeDir $runtimeDir -BackendPort $backendPort -FrontendPort $frontendPort -PrimaryUrl "$frontendUrl/" -Mode "source"
Open-UrlDetached $frontendUrl
exit 0
