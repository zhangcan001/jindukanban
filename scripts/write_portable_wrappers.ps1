param(
  [Parameter(Mandatory = $true)][string]$Target,
  [Parameter(Mandatory = $true)][string]$Version
)

$wrappers = @(
  "start.bat",
  "stop.bat",
  "restart.bat",
  "backup.bat",
  "restore_guide.bat",
  "diagnose.bat",
  "create_shortcut.bat"
)

foreach ($scriptName in $wrappers) {
  $content = @(
    "@echo off",
    "setlocal EnableExtensions",
    "echo progress-dashboard $Version portable",
    "call ""%~dp0scripts\$scriptName"" %*"
  )
  $content | Set-Content -Path (Join-Path $Target $scriptName) -Encoding ASCII
}
