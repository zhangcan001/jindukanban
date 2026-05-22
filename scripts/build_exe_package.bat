@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "VERSION=v4.9-exe-launcher"
set "TARGET=%ROOT%\release\工程进度管理系统-%VERSION%"

echo ========================================
echo progress-dashboard %VERSION% exe package build
echo ========================================

echo [1/4] run frontend npm run build...
pushd "%ROOT%\frontend"
call npm run build
set "BUILD_EXIT=%ERRORLEVEL%"
popd
if not "%BUILD_EXIT%"=="0" (
  echo [ERROR] npm run build failed.
  exit /b 1
)

echo [2/4] build installer-lite style package...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\build_installer_lite.ps1" -Root "%ROOT%" -Version "%VERSION%" -PackageType "exe-launcher"
if errorlevel 1 (
  echo [ERROR] package assembly failed.
  exit /b 1
)

echo [3/4] build exe launcher...
call "%ROOT%\scripts\build_exe_launcher.bat" "%TARGET%"
if errorlevel 1 (
  echo [ERROR] exe launcher build failed.
  exit /b 1
)

echo [4/4] verify exe package...
if not exist "%TARGET%\工程进度管理系统.exe" (
  echo [ERROR] exe not found in package.
  exit /b 1
)
if not exist "%TARGET%\app\frontend_dist\index.html" (
  echo [ERROR] frontend_dist missing.
  exit /b 1
)
if not exist "%TARGET%\app\backend\.venv\Scripts\python.exe" (
  echo [ERROR] backend venv missing.
  exit /b 1
)

echo.
echo EXE package generated:
echo %TARGET%
exit /b 0

