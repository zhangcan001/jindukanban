@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
if not exist "%ROOT%\start.bat" if exist "%~dp0start.bat" (
  set "ROOT=%~dp0"
  for %%I in ("%ROOT%") do set "ROOT=%%~fI"
)

set "START_BAT=%ROOT%\start.bat"
set "SHORTCUT_NAME=工程进度管理系统.lnk"
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT_PATH=%DESKTOP%\%SHORTCUT_NAME%"

echo ========================================
echo 创建工程进度管理系统桌面快捷方式
echo ========================================

if not exist "%START_BAT%" (
  echo [错误] 未找到启动脚本：%START_BAT%
  echo 请确认本脚本位于项目 scripts 目录或 portable 包根目录。
  pause
  exit /b 1
)

if not exist "%DESKTOP%" (
  echo [错误] 未找到桌面目录：%DESKTOP%
  pause
  exit /b 1
)

if exist "%SHORTCUT_PATH%" (
  set /p "OVERWRITE=桌面快捷方式已存在，是否覆盖？(Y/N)："
  if /I not "%OVERWRITE%"=="Y" (
    echo 已取消创建快捷方式。
    pause
    exit /b 0
  )
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$shell = New-Object -ComObject WScript.Shell; " ^
  "$shortcut = $shell.CreateShortcut('%SHORTCUT_PATH%'); " ^
  "$shortcut.TargetPath = '%START_BAT%'; " ^
  "$shortcut.WorkingDirectory = '%ROOT%'; " ^
  "$shortcut.IconLocation = '%SystemRoot%\System32\SHELL32.dll,167'; " ^
  "$shortcut.Description = '工程进度管理系统'; " ^
  "$shortcut.Save()"

if errorlevel 1 (
  echo [错误] 快捷方式创建失败，请确认 PowerShell 可用且桌面目录可写。
  pause
  exit /b 1
)

echo [完成] 已创建桌面快捷方式：
echo %SHORTCUT_PATH%
pause
exit /b 0
