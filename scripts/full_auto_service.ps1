param(
  [ValidateSet("HasProjectService", "RunPytest", "UpdateLatestReport")]
  [string]$Action,
  [string]$Root,
  [string]$PythonExe = "",
  [string]$StoppedAfter = ""
)

$ErrorActionPreference = "Continue"

$resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
$runtimeDir = Join-Path $resolvedRoot ".runtime"

function Test-ProjectService {
  $normalizedRoot = $resolvedRoot.ToLowerInvariant()
  foreach ($port in @(8000, 5173)) {
    $connections = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
      $process = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $connection.OwningProcess) -ErrorAction SilentlyContinue
      $commandLine = if ($process) { [string]$process.CommandLine } else { "" }
      if ($commandLine.ToLowerInvariant().Contains($normalizedRoot)) {
        return $true
      }
    }
  }

  return (Test-Path -LiteralPath (Join-Path $runtimeDir "backend.pid")) -or (Test-Path -LiteralPath (Join-Path $runtimeDir "frontend.pid"))
}

function Update-LatestReport {
  $reportDir = Join-Path $resolvedRoot "test_reports"
  $report = Get-ChildItem -LiteralPath $reportDir -Filter "full_auto_check_*.md" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if (-not $report) {
    return
  }

  $text = Get-Content -LiteralPath $report.FullName -Raw -Encoding UTF8
  $text = $text -replace "- 结束后是否停止：.*", ("- 结束后是否停止：" + $StoppedAfter)
  Set-Content -LiteralPath $report.FullName -Value $text -Encoding UTF8
}

function Invoke-PytestWithRetry {
  if (-not $PythonExe) {
    Write-Host "[ERROR] PythonExe is required."
    exit 1
  }
  $isInstallerLite = Test-Path -LiteralPath (Join-Path $resolvedRoot "INSTALLER_LITE")
  $isExeLauncher = Test-Path -LiteralPath (Join-Path $resolvedRoot "EXE_LAUNCHER")
  $isPortableRelease = ((Test-Path -LiteralPath (Join-Path $resolvedRoot "frontend_dist")) -and (Test-Path -LiteralPath (Join-Path $resolvedRoot "data")) -and ($resolvedRoot.ToLowerInvariant().Contains("\release\")))
  if ($isInstallerLite -or $isExeLauncher -or $isPortableRelease) {
    Write-Host "release package has no full test source; skip pytest and run API acceptance."
    exit 0
  }
  $testPath = Join-Path $resolvedRoot "backend\tests"
  if (-not (Test-Path -LiteralPath $testPath)) {
    Write-Host "release package has no full test source; skip pytest and run API acceptance."
    exit 0
  }

  Push-Location $resolvedRoot
  try {
    $output = & $PythonExe -m pytest "backend\tests" 2>&1
    $exitCode = $LASTEXITCODE
    $output | ForEach-Object { Write-Host $_ }
    $joined = ($output | Out-String)
    if ($exitCode -ne 0 -and $joined.Contains("WinError 10055")) {
      Write-Host ""
      Write-Host "[retry] detected WinError 10055, cleaning project services and waiting before pytest retry..."
      & (Join-Path $resolvedRoot "scripts\stop.bat")
      Start-Sleep -Seconds 30
      $output = & $PythonExe -m pytest "backend\tests" 2>&1
      $exitCode = $LASTEXITCODE
      $output | ForEach-Object { Write-Host $_ }
    }
  } finally {
    Pop-Location
  }

  exit $exitCode
}

if ($Action -eq "HasProjectService") {
  if (Test-ProjectService) {
    exit 0
  }
  exit 1
}

if ($Action -eq "RunPytest") {
  Invoke-PytestWithRetry
}

if ($Action -eq "UpdateLatestReport") {
  Update-LatestReport
  exit 0
}
