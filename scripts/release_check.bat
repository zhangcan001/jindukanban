@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

echo ========================================
echo v5.0-desktop-shell release_check
echo ========================================

call "%ROOT%\scripts\quick_check.bat"
if not "%ERRORLEVEL%"=="0" (
  echo.
  echo release_check 失败：quick_check 未通过。
  exit /b %ERRORLEVEL%
)

set "MISSING=0"
echo.
echo [发布文件检查]

if exist "%ROOT%\README.md" (
  echo README.md：存在
) else (
  echo README.md：缺失
  set "MISSING=1"
)

if exist "%ROOT%\RELEASE_NOTES.md" (
  echo RELEASE_NOTES.md：存在
) else (
  echo RELEASE_NOTES.md：缺失
  set "MISSING=1"
)

if exist "%ROOT%\scripts\start.bat" (
  echo scripts\start.bat：存在
) else (
  echo scripts\start.bat：缺失
  set "MISSING=1"
)

if exist "%ROOT%\scripts\backup.bat" (
  echo scripts\backup.bat：存在
) else (
  echo scripts\backup.bat：缺失
  set "MISSING=1"
)

if exist "%ROOT%\scripts\build_portable.bat" (
  echo scripts\build_portable.bat：存在
) else (
  echo scripts\build_portable.bat：缺失
  set "MISSING=1"
)

echo.
if "%MISSING%"=="0" (
  echo release_check 通过。
  echo 发布检查结果：建议继续发布收尾。
  exit /b 0
)

echo release_check 失败：存在必要文件缺失。
echo 发布检查结果：不建议继续发布。
exit /b 1




