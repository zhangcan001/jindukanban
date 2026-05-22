@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup.ps1" -Root "%ROOT%"
if errorlevel 1 (
  echo [错误] 备份失败，请查看控制台输出和 logs 目录中的诊断日志。
  exit /b 1
)
exit /b 0
