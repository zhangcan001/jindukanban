@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "PYTHON_EXE=%ROOT%\backend\.venv\Scripts\python.exe"

echo ========================================
echo v5.0-desktop-shell quick_check
echo ========================================

if not exist "%PYTHON_EXE%" (
  echo quick_check failed: backend venv not found.
  exit /b 1
)

echo [1/2] run backend pytest...
if exist "%ROOT%\backend\tests" (
  pushd "%ROOT%"
  "%PYTHON_EXE%" -m pytest backend\tests
  set "PYTEST_EXIT=%ERRORLEVEL%"
  popd
) else (
  echo backend tests not packaged, pytest skipped.
  set "PYTEST_EXIT=0"
)
if not "!PYTEST_EXIT!"=="0" (
  echo.
  echo quick_check failed: pytest failed.
  echo pytest: FAIL
  echo npm run build: NOT RUN
  echo continue: NO
  exit /b !PYTEST_EXIT!
)

echo.
if exist "%ROOT%\frontend\package.json" (
  echo [2/2] run frontend npm run build...
  pushd "%ROOT%\frontend"
  call npm run build
  set "BUILD_EXIT=%ERRORLEVEL%"
  popd
) else if exist "%ROOT%\frontend_dist\index.html" (
  echo [2/2] validate frontend_dist...
  set "BUILD_EXIT=0"
) else (
  echo [2/2] frontend build artifact missing.
  set "BUILD_EXIT=1"
)
if not "!BUILD_EXIT!"=="0" (
  echo.
  echo quick_check failed: npm run build failed.
  echo pytest: PASS
  echo npm run build: FAIL
  echo continue: NO
  exit /b !BUILD_EXIT!
)

echo.
echo quick_check passed.
echo pytest: PASS
echo npm run build: PASS
echo continue: YES
echo.
echo Full auto check command:
echo scripts\full_auto_check.bat
exit /b 0




