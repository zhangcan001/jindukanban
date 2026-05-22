@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%ROOT%\release\工程进度管理系统-v4.9-exe-launcher"
set "LAUNCHER=%ROOT%\launcher\exe_launcher.py"
set "BUILD_DIR=%ROOT%\.runtime\pyinstaller_build"
set "DIST_DIR=%ROOT%\.runtime\pyinstaller_dist"
set "EXE_NAME=工程进度管理系统"

echo ========================================
echo build exe launcher
echo ========================================

if not exist "%LAUNCHER%" (
  echo [ERROR] launcher source not found: %LAUNCHER%
  exit /b 1
)
if not exist "%TARGET%" (
  echo [ERROR] target package not found: %TARGET%
  exit /b 1
)

python -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo [INFO] PyInstaller not found, installing...
  python -m pip install pyinstaller
  if errorlevel 1 (
    echo [ERROR] failed to install PyInstaller.
    exit /b 1
  )
)

if exist "%BUILD_DIR%" rmdir /S /Q "%BUILD_DIR%"
if exist "%DIST_DIR%" rmdir /S /Q "%DIST_DIR%"
mkdir "%BUILD_DIR%" "%DIST_DIR%" >nul 2>nul

python -m PyInstaller ^
  --onefile ^
  --console ^
  --name "%EXE_NAME%" ^
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
if not exist "%TARGET%\%EXE_NAME%.exe" (
  echo [ERROR] exe missing after build.
  exit /b 1
)

echo EXE launcher generated:
echo %TARGET%\%EXE_NAME%.exe
exit /b 0

