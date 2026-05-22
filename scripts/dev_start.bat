@echo off
setlocal EnableExtensions

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev_start.ps1"
exit /b %ERRORLEVEL%
