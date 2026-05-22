@echo off
setlocal EnableExtensions

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
exit /b %ERRORLEVEL%
