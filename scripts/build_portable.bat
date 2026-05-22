@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "PACKAGE_VERSION=v4.9-exe-launcher"
set "VERSION=v4.9-exe-launcher"
set "RELEASE_ROOT=%ROOT%\release"
set "TARGET=%RELEASE_ROOT%\progress-dashboard-%PACKAGE_VERSION%"
set "FRONTEND_DIST=%ROOT%\frontend\dist"

echo ========================================
echo progress-dashboard %VERSION% portable build
echo ========================================

if not exist "%ROOT%\backend\app\main.py" (
  echo [ERROR] backend\app\main.py not found.
  exit /b 1
)
if not exist "%FRONTEND_DIST%\index.html" (
  echo [ERROR] frontend\dist not found. Run npm build first.
  exit /b 1
)
if not exist "%ROOT%\backend\.venv\Scripts\python.exe" (
  echo [WARN] backend virtualenv not found.
)

if exist "%TARGET%" (
  echo [INFO] remove old target: %TARGET%
  rmdir /S /Q "%TARGET%"
)
mkdir "%TARGET%" >nul 2>nul
mkdir "%TARGET%\frontend_dist" "%TARGET%\scripts" "%TARGET%\docs" "%TARGET%\data" "%TARGET%\uploads" "%TARGET%\exports" "%TARGET%\backups" "%TARGET%\logs" >nul 2>nul

echo [1/7] Copy backend...
robocopy "%ROOT%\backend" "%TARGET%\backend" /E /XD "__pycache__" ".pytest_cache" "uploads" "reports" "backups" /XF "*.pyc" "*.pyo" "progress_dashboard.db" "test_progress_dashboard.db" "*.log" "*.out.log" "*.err.log" >nul
if errorlevel 8 (
  echo [ERROR] backend copy failed.
  exit /b 1
)

echo [2/7] Copy frontend dist...
robocopy "%FRONTEND_DIST%" "%TARGET%\frontend_dist" /E >nul
if errorlevel 8 (
  echo [ERROR] frontend dist copy failed.
  exit /b 1
)

echo [3/7] Copy scripts...
robocopy "%ROOT%\scripts" "%TARGET%\scripts" /E /XF "*.pyc" "*.pyo" "*.log" "*.out.log" "*.err.log" >nul
if errorlevel 8 (
  echo [ERROR] scripts copy failed.
  exit /b 1
)

echo [4/7] Copy docs and sample data...
copy "%ROOT%\README.md" "%TARGET%\docs\README.md" >nul
copy "%ROOT%\BACKUP.md" "%TARGET%\docs\BACKUP.md" >nul
copy "%ROOT%\DEPLOYMENT.md" "%TARGET%\docs\DEPLOYMENT.md" >nul
copy "%ROOT%\RELEASE_NOTES.md" "%TARGET%\docs\RELEASE_NOTES.md" >nul
robocopy "%ROOT%\samples" "%TARGET%\samples" /E >nul
if errorlevel 8 (
  echo [ERROR] samples copy failed.
  exit /b 1
)
robocopy "%ROOT%\sample_data" "%TARGET%\sample_data" /E >nul
if errorlevel 8 (
  echo [ERROR] sample_data copy failed.
  exit /b 1
)
if exist "%ROOT%\.env.example" copy "%ROOT%\.env.example" "%TARGET%\.env.example" >nul

echo [5/7] Write portable env...
(
  echo APP_NAME=progress-dashboard
  echo APP_ENV=production
  echo DATABASE_URL=sqlite:///../data/progress_dashboard.db
  echo UPLOAD_DIR=../uploads
  echo EXPORT_DIR=../exports
  echo BACKUP_DIR=../backups
  echo MAX_UPLOAD_SIZE_MB=20
  echo BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
  echo LOG_LEVEL=INFO
) > "%TARGET%\backend\.env"

echo [6/7] Write root wrappers...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\write_portable_wrappers.ps1" -Target "%TARGET%" -Version "%VERSION%"
if errorlevel 1 (
  echo [ERROR] wrapper generation failed.
  exit /b 1
)
copy "%ROOT%\scripts\README_??????.md" "%TARGET%\README_??????.md" >nul

echo [7/7] Write package_info.txt...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\write_package_info.ps1" -Target "%TARGET%" -Version "%VERSION%" -Root "%ROOT%"
if errorlevel 1 (
  echo [ERROR] package_info generation failed.
  exit /b 1
)

for /r "%TARGET%" %%F in (*.pyc *.pyo *.log *.out.log *.err.log) do del /q "%%F" >nul 2>nul
for /d /r "%TARGET%" %%D in (__pycache__ .pytest_cache) do if exist "%%D" rmdir /s /q "%%D"

echo.
echo Portable package generated:
echo %TARGET%
exit /b 0


