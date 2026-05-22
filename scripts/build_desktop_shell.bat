@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "VERSION=v5.0-desktop-shell"
set "TARGET=%ROOT%\release\工程进度管理系统-%VERSION%"
set "LAUNCHER=%ROOT%\launcher\desktop_launcher.py"
set "BUILD_DIR=%ROOT%\.runtime\pyinstaller_desktop_build"
set "DIST_DIR=%ROOT%\.runtime\pyinstaller_desktop_dist"
set "EXE_NAME=工程进度管理系统"
set "BUILD_PY=python"

echo ========================================
echo progress-dashboard %VERSION% desktop shell build
echo ========================================

if not exist "%LAUNCHER%" (
  echo [ERROR] desktop launcher source not found: %LAUNCHER%
  exit /b 1
)

echo [1/5] run frontend npm run build...
pushd "%ROOT%\frontend"
call npm run build
set "BUILD_EXIT=%ERRORLEVEL%"
popd
if not "%BUILD_EXIT%"=="0" (
  echo [ERROR] npm run build failed.
  exit /b 1
)
if not exist "%ROOT%\frontend\dist\index.html" (
  echo [ERROR] frontend dist missing.
  exit /b 1
)

echo [2/5] assemble desktop-shell package...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\build_installer_lite.ps1" -Root "%ROOT%" -Version "%VERSION%" -PackageType "desktop-shell"
if errorlevel 1 (
  echo [ERROR] package assembly failed.
  exit /b 1
)

echo [3/5] check Python desktop dependencies...
py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  set "BUILD_PY=py -3.12"
)
echo Desktop launcher build Python: %BUILD_PY%

%BUILD_PY% -c "import webview" >nul 2>nul
if errorlevel 1 (
  echo [INFO] pywebview not found, installing...
  %BUILD_PY% -m pip install pywebview
  if errorlevel 1 (
    echo [ERROR] failed to install pywebview.
    exit /b 1
  )
)
%BUILD_PY% -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo [INFO] PyInstaller not found, installing...
  %BUILD_PY% -m pip install pyinstaller
  if errorlevel 1 (
    echo [ERROR] failed to install PyInstaller.
    exit /b 1
  )
)

echo [4/5] build desktop shell exe...
if exist "%BUILD_DIR%" rmdir /S /Q "%BUILD_DIR%"
if exist "%DIST_DIR%" rmdir /S /Q "%DIST_DIR%"
mkdir "%BUILD_DIR%" "%DIST_DIR%" >nul 2>nul

%BUILD_PY% -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name "%EXE_NAME%" ^
  --collect-submodules webview ^
  --distpath "%DIST_DIR%" ^
  --workpath "%BUILD_DIR%" ^
  --specpath "%BUILD_DIR%" ^
  "%LAUNCHER%"
if errorlevel 1 (
  echo [ERROR] PyInstaller build failed.
  exit /b 1
)

copy /Y "%DIST_DIR%\%EXE_NAME%.exe" "%TARGET%\%EXE_NAME%.exe" >nul
if errorlevel 1 (
  echo [ERROR] failed to copy exe to package root.
  exit /b 1
)

echo [5/5] verify desktop-shell package...
if not exist "%TARGET%\工程进度管理系统.exe" (
  echo [ERROR] exe not found in package.
  exit /b 1
)
if not exist "%TARGET%\app\frontend_dist\index.html" (
  echo [ERROR] frontend_dist missing.
  exit /b 1
)
if not exist "%TARGET%\app\frontend_dist\assets" (
  echo [ERROR] frontend_dist assets missing.
  exit /b 1
)
dir /B "%TARGET%\app\frontend_dist\assets\*" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] frontend_dist assets empty.
  exit /b 1
)
if not exist "%TARGET%\app\backend\.venv\Scripts\python.exe" (
  echo [ERROR] backend venv missing.
  exit /b 1
)
if not exist "%TARGET%\app\DESKTOP_SHELL" (
  echo [ERROR] DESKTOP_SHELL marker missing.
  exit /b 1
)

echo.
echo Desktop shell package generated:
echo %TARGET%
exit /b 0

