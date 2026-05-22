@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "VERSION=v4.9-exe-launcher"

echo ========================================
echo progress-dashboard %VERSION% installer-lite build
echo ========================================

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\build_installer_lite.ps1" -Root "%ROOT%" -Version "%VERSION%"
if errorlevel 1 (
  echo [ERROR] installer-lite build failed.
  exit /b 1
)

exit /b 0


