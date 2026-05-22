@echo off
setlocal EnableExtensions

echo ========================================
echo 工程进度看板 v5.0-desktop-shell 重启服务
echo ========================================

call "%~dp0stop.bat"
if errorlevel 1 (
  echo [错误] 停止服务失败，请根据上方提示处理后再重试。
  exit /b 1
)

timeout /t 2 /nobreak >nul

call "%~dp0start.bat"
if errorlevel 1 (
  echo [错误] 启动服务失败，请根据上方阶段提示处理。
  exit /b 1
)

echo 重启完成。
exit /b 0









