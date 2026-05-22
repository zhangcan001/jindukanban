@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "PYTHON_EXE=%ROOT%\backend\.venv\Scripts\python.exe"
set "RUNTIME_DIR=%ROOT%\.runtime"
if exist "%ROOT%\frontend\package.json" (
  set "FULL_AUTO_PACKAGE_MODE=source"
) else if exist "%ROOT%\EXE_LAUNCHER" (
  set "FULL_AUTO_PACKAGE_MODE=exe-launcher"
) else if exist "%ROOT%\DESKTOP_SHELL" (
  set "FULL_AUTO_PACKAGE_MODE=desktop-shell"
) else if exist "%ROOT%\INSTALLER_LITE" (
  set "FULL_AUTO_PACKAGE_MODE=installer-lite"
) else if exist "%ROOT%\frontend_dist\index.html" (
  set "FULL_AUTO_PACKAGE_MODE=portable"
) else (
  set "FULL_AUTO_PACKAGE_MODE=unknown"
)

echo ========================================
echo full_auto_check
echo ========================================

if not exist "%PYTHON_EXE%" (
  echo [ERROR] backend venv not found: %ROOT%\backend\.venv
  exit /b 1
)

set "SKIP_PYTEST=0"
if /I "%~1"=="--skip-pytest" set "SKIP_PYTEST=1"

set "FULL_AUTO_OLD_SERVICE_FOUND=否"
set "FULL_AUTO_OLD_SERVICE_CLEANED=否"
set "FULL_AUTO_BACKEND_PID=-"
set "FULL_AUTO_FRONTEND_PID=-"
set "FULL_AUTO_STOPPED_AFTER=否"

echo [pre] check existing project services...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\full_auto_service.ps1" -Action HasProjectService -Root "%ROOT%"
if "%ERRORLEVEL%"=="0" (
  set "FULL_AUTO_OLD_SERVICE_FOUND=是"
  echo [pre] found existing project services, cleaning...
  call "%ROOT%\scripts\stop.bat"
  if errorlevel 1 (
    echo [ERROR] failed to clean existing project services.
    exit /b 1
  )
  set "FULL_AUTO_OLD_SERVICE_CLEANED=是"
) else (
  echo [pre] no existing project services found.
)

if exist "%ROOT%\scripts\generate_full_test_excel.py" (
  echo [0/5] ensure full test Excel...
  "%PYTHON_EXE%" "%ROOT%\scripts\generate_full_test_excel.py"
  if errorlevel 1 (
    echo [ERROR] failed to generate full test Excel.
    echo Please put the file under sample_data manually.
    exit /b 1
  )
) else (
  echo [ERROR] generator script not found.
  echo Please put it under sample_data manually.
  exit /b 1
)

echo.
echo [1/5] run backend pytest...
if "%SKIP_PYTEST%"=="1" (
  echo pytest skipped by --skip-pytest.
  set "PYTEST_EXIT=0"
  set "FULL_AUTO_PYTEST_STATUS=SKIPPED"
) else if not exist "%ROOT%\backend\tests" (
  echo release package has no full test source; skip pytest and run API acceptance.
  set "PYTEST_EXIT=0"
  set "FULL_AUTO_PYTEST_STATUS=SKIPPED"
) else if not "%FULL_AUTO_PACKAGE_MODE%"=="source" (
  echo release package has no full test source; skip pytest and run API acceptance.
  set "PYTEST_EXIT=0"
  set "FULL_AUTO_PYTEST_STATUS=SKIPPED"
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\full_auto_service.ps1" -Action RunPytest -Root "%ROOT%" -PythonExe "%PYTHON_EXE%"
  set "PYTEST_EXIT=%ERRORLEVEL%"
  if errorlevel 1 (
    set "FULL_AUTO_PYTEST_STATUS=FAIL"
  ) else (
    set "FULL_AUTO_PYTEST_STATUS=PASS"
  )
)

echo.
if "%FULL_AUTO_PACKAGE_MODE%"=="source" (
  echo [2/5] run frontend npm run build...
  pushd "%ROOT%\frontend"
  call npm run build
  set "BUILD_EXIT=%ERRORLEVEL%"
  popd
) else if "%FULL_AUTO_PACKAGE_MODE%"=="portable" (
  echo [2/5] validate frontend_dist...
  set "BUILD_EXIT=0"
) else if "%FULL_AUTO_PACKAGE_MODE%"=="exe-launcher" (
  echo [2/5] validate frontend_dist...
  set "BUILD_EXIT=0"
) else if "%FULL_AUTO_PACKAGE_MODE%"=="desktop-shell" (
  echo [2/5] validate frontend_dist...
  set "BUILD_EXIT=0"
) else if "%FULL_AUTO_PACKAGE_MODE%"=="installer-lite" (
  echo [2/5] validate frontend_dist...
  set "BUILD_EXIT=0"
) else (
  echo [2/5] frontend artifact missing.
  set "BUILD_EXIT=1"
)
if errorlevel 1 (
  set "FULL_AUTO_BUILD_STATUS=FAIL"
) else (
  set "FULL_AUTO_BUILD_STATUS=PASS"
)

echo.
echo [3/5] start backend and frontend...
if "%FULL_AUTO_PACKAGE_MODE%"=="source" (
  call "%ROOT%\scripts\dev_start.bat"
) else (
  call "%ROOT%\scripts\start.bat"
)
set "START_EXIT=%ERRORLEVEL%"
if "%START_EXIT%"=="0" (
  set "FULL_AUTO_START_STATUS=PASS"
) else (
  set "FULL_AUTO_START_STATUS=FAIL"
)
if exist "%RUNTIME_DIR%\backend.pid" set /p FULL_AUTO_BACKEND_PID=<"%RUNTIME_DIR%\backend.pid"
if exist "%RUNTIME_DIR%\frontend.pid" set /p FULL_AUTO_FRONTEND_PID=<"%RUNTIME_DIR%\frontend.pid"

echo.
echo [4/5] check backend health...
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 5; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 300){ exit 0 } }; exit 1" >nul 2>nul
if "%ERRORLEVEL%"=="0" (
  set "FULL_AUTO_HEALTH_STATUS=PASS"
) else (
  set "FULL_AUTO_HEALTH_STATUS=FAIL"
)

if "%FULL_AUTO_PACKAGE_MODE%"=="desktop-shell" (
  powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -UseBasicParsing -TimeoutSec 5; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 500){ exit 0 } }; exit 1" >nul 2>nul
) else (
  powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 5; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 500){ exit 0 } }; exit 1" >nul 2>nul
)
if "%ERRORLEVEL%"=="0" (
  set "FULL_AUTO_FRONTEND_STATUS=PASS"
) else (
  set "FULL_AUTO_FRONTEND_STATUS=FAIL"
)

echo.
echo [5/5] run API acceptance and write report...
set "FULL_AUTO_PYTEST_EXIT=%PYTEST_EXIT%"
set "FULL_AUTO_BUILD_EXIT=%BUILD_EXIT%"
set "FULL_AUTO_START_EXIT=%START_EXIT%"
"%PYTHON_EXE%" "%ROOT%\scripts\full_auto_check.py"
set "CHECK_EXIT=%ERRORLEVEL%"

echo.
choice /C YN /N /T 15 /D Y /M "Stop project services? [Y/N] default Y: "
if "%ERRORLEVEL%"=="1" (
  call "%ROOT%\scripts\stop.bat"
  if errorlevel 1 (
    set "FULL_AUTO_STOPPED_AFTER=停止失败"
  ) else (
    set "FULL_AUTO_STOPPED_AFTER=是"
  )
  powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\full_auto_service.ps1" -Action UpdateLatestReport -Root "%ROOT%" -StoppedAfter "!FULL_AUTO_STOPPED_AFTER!"
  set "CHECK_EXIT=%CHECK_EXIT%"
  exit /b %CHECK_EXIT%
)
set "FULL_AUTO_STOPPED_AFTER=否"
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\full_auto_service.ps1" -Action UpdateLatestReport -Root "%ROOT%" -StoppedAfter "%FULL_AUTO_STOPPED_AFTER%"

exit /b %CHECK_EXIT%
