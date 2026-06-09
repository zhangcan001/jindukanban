@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\frontend"
set "FRONTEND_DIST_DIR=%ROOT%\frontend_dist"
set "VITE_CMD=%FRONTEND_DIR%\node_modules\.bin\vite.cmd"
set "RUNTIME_DIR=%ROOT%\.runtime"
set "LOG_DIR=%ROOT%\logs"
if not defined BACKEND_PORT set "BACKEND_PORT=8000"
if not defined FRONTEND_PORT set "FRONTEND_PORT=5173"
set "BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%"
set "FRONTEND_URL=http://127.0.0.1:%FRONTEND_PORT%"
set "IS_DESKTOP_SHELL=0"
if exist "%ROOT%\DESKTOP_SHELL" set "IS_DESKTOP_SHELL=1"

echo ========================================
echo 工程进度看板 v5.0-desktop-shell 一键启动
echo Backend URL %BACKEND_URL%
if "%IS_DESKTOP_SHELL%"=="1" goto echo_desktop_frontend_url
echo Frontend URL %FRONTEND_URL%
goto echo_frontend_url_done
:echo_desktop_frontend_url
echo Frontend URL %BACKEND_URL%/
:echo_frontend_url_done
echo ========================================
echo 正在检查运行环境...

if "%IS_DESKTOP_SHELL%"=="1" goto desktop_shell_start

if not exist "%BACKEND_DIR%\app\main.py" (
  echo [错误] 当前目录不是项目根目录，未找到 backend\app\main.py。
  exit /b 1
)
if exist "%FRONTEND_DIST_DIR%\index.html" (
  if exist "%ROOT%\DESKTOP_SHELL" (
    set "FRONTEND_MODE=backend-static"
    echo 当前模式：desktop-shell 后端托管前端
  ) else (
    set "FRONTEND_MODE=portable"
    echo 当前模式：portable 便携版
  )
) else if exist "%FRONTEND_DIR%\package.json" (
  set "FRONTEND_MODE=source"
  echo 当前模式：源码开发版
) else (
  echo [错误] 未找到 frontend_dist\index.html 或 frontend\package.json。
  exit /b 1
)
if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" >nul 2>nul
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul
call :try_reuse_runtime_state
if "%RUNTIME_READY%"=="1" exit /b 0
if exist "%FRONTEND_DIST_DIR%\index.html" (
  if not exist "%ROOT%\data" mkdir "%ROOT%\data" >nul 2>nul
  if not exist "%ROOT%\uploads" mkdir "%ROOT%\uploads" >nul 2>nul
  if not exist "%ROOT%\exports" mkdir "%ROOT%\exports" >nul 2>nul
  if not exist "%ROOT%\backups" mkdir "%ROOT%\backups" >nul 2>nul
)

set "PYTHON_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe"
if exist "%PYTHON_EXE%" (
  echo 后端虚拟环境：已找到
) else (
  echo [错误] 后端虚拟环境不存在：%BACKEND_DIR%\.venv
  echo        请先创建虚拟环境并安装 backend\requirements.txt。
  exit /b 1
)

"%PYTHON_EXE%" -c "import fastapi, sqlalchemy, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo [错误] 后端依赖不可用，请在 backend 目录执行：
  echo        .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)
echo 后端依赖：已找到

if "%FRONTEND_MODE%"=="source" (
  where node >nul 2>nul
  if errorlevel 1 (
    echo [错误] 未找到 node，请先安装 Node.js 或确认 node 在 PATH 中。
    exit /b 1
  )
  if exist "%FRONTEND_DIR%\node_modules" (
    echo 前端依赖：已找到
  ) else (
    echo [错误] 前端依赖不存在：%FRONTEND_DIR%\node_modules
    echo        请先在 frontend 目录执行 npm install。
    exit /b 1
  )
  if not exist "%VITE_CMD%" (
    echo [错误] 未找到 Vite 启动脚本：%VITE_CMD%
    echo        请先在 frontend 目录执行 npm install。
    exit /b 1
  )
)
if "%FRONTEND_MODE%"=="portable" (
  echo 前端构建产物：已找到
)

call :pick_port "%BACKEND_PORT%" "后端" BACKEND_PORT
if "%ERRORLEVEL%"=="1" exit /b 1
set "BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%"
if not "%FRONTEND_MODE%"=="backend-static" (
  call :pick_port "%FRONTEND_PORT%" "前端" FRONTEND_PORT
  if "%ERRORLEVEL%"=="1" exit /b 1
  set "FRONTEND_URL=http://127.0.0.1:!FRONTEND_PORT!"
)

echo 正在启动后端...
set "BACKEND_OUT=%RUNTIME_DIR%\backend.out.log"
set "BACKEND_ERR=%RUNTIME_DIR%\backend.err.log"
powershell -NoProfile -Command "$p=Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','%BACKEND_PORT%') -WorkingDirectory '%BACKEND_DIR%' -RedirectStandardOutput '%BACKEND_OUT%' -RedirectStandardError '%BACKEND_ERR%' -PassThru -WindowStyle Hidden; Set-Content -Path '%RUNTIME_DIR%\backend.pid' -Value $p.Id" >nul 2>nul
if errorlevel 1 (
  echo [错误] 后端启动命令执行失败。
  exit /b 1
)
if not exist "%RUNTIME_DIR%\backend.pid" (
  echo [错误] 后端 PID 写入失败。
  exit /b 1
)

call :wait_url "%BACKEND_URL%/api/health" 后端健康检查
if "%URL_READY%"=="0" (
  echo [错误] 后端健康检查未通过，请查看日志：
  echo        %BACKEND_ERR%
  exit /b 1
)
call :write_listening_pid %BACKEND_PORT% "%RUNTIME_DIR%\backend.pid" 后端
echo 后端健康检查通过

if "%FRONTEND_MODE%"=="backend-static" (
  echo 前端由后端统一托管：%BACKEND_URL%/
  call :wait_url "%BACKEND_URL%/" 前端首页检查
  if "%URL_READY%"=="0" (
    echo [错误] 前端首页未就绪，请查看日志：
    echo        %BACKEND_ERR%
    exit /b 1
  )
) else (
  echo 正在启动前端...
  set "FRONTEND_OUT=%RUNTIME_DIR%\frontend.out.log"
  set "FRONTEND_ERR=%RUNTIME_DIR%\frontend.err.log"
  if "%FRONTEND_MODE%"=="source" (
    powershell -NoProfile -Command "$env:VITE_API_BASE_URL='%BACKEND_URL%'; $p=Start-Process -FilePath '%VITE_CMD%' -ArgumentList @('--host','127.0.0.1','--port','%FRONTEND_PORT%') -WorkingDirectory '%FRONTEND_DIR%' -RedirectStandardOutput '%FRONTEND_OUT%' -RedirectStandardError '%FRONTEND_ERR%' -PassThru -WindowStyle Hidden; Set-Content -Path '%RUNTIME_DIR%\frontend.pid' -Value $p.Id" >nul 2>nul
  ) else (
    powershell -NoProfile -Command "$p=Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList @('-m','http.server','%FRONTEND_PORT%','--bind','127.0.0.1','--directory','%FRONTEND_DIST_DIR%') -WorkingDirectory '%ROOT%' -RedirectStandardOutput '%FRONTEND_OUT%' -RedirectStandardError '%FRONTEND_ERR%' -PassThru -WindowStyle Hidden; Set-Content -Path '%RUNTIME_DIR%\frontend.pid' -Value $p.Id" >nul 2>nul
  )
  if errorlevel 1 (
    echo [错误] 前端启动命令执行失败。
    exit /b 1
  )
  if not exist "%RUNTIME_DIR%\frontend.pid" (
    echo [错误] 前端 PID 写入失败。
    exit /b 1
  )

  call :wait_url "%FRONTEND_URL%/" 前端端口检查
  if "%URL_READY%"=="0" (
    echo [错误] 前端端口未就绪，请查看日志：
    echo        %FRONTEND_ERR%
    exit /b 1
  )
  call :write_listening_pid %FRONTEND_PORT% "%RUNTIME_DIR%\frontend.pid" 前端
)

echo 系统已启动
if "%FRONTEND_MODE%"=="backend-static" (
  set "PRIMARY_URL=%BACKEND_URL%/"
) else (
  set "PRIMARY_URL=%FRONTEND_URL%/"
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0write_runtime_state.ps1" -RuntimeDir "%RUNTIME_DIR%" -BackendPort %BACKEND_PORT% -FrontendPort %FRONTEND_PORT% -PrimaryUrl "%PRIMARY_URL%" -Mode "%FRONTEND_MODE%" >nul 2>nul
echo 访问地址：%PRIMARY_URL%
start "" "%PRIMARY_URL%"
exit /b 0

:desktop_shell_start
echo Mode: desktop-shell backend static frontend
if not exist "%BACKEND_DIR%\app\main.py" (
  echo [ERROR] backend app not found.
  exit /b 1
)
if not exist "%FRONTEND_DIST_DIR%\index.html" (
  echo [ERROR] frontend_dist index.html not found.
  exit /b 1
)
if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" >nul 2>nul
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul
call :try_reuse_runtime_state
if "%RUNTIME_READY%"=="1" exit /b 0
if not exist "%ROOT%\data" mkdir "%ROOT%\data" >nul 2>nul
if not exist "%ROOT%\uploads" mkdir "%ROOT%\uploads" >nul 2>nul
if not exist "%ROOT%\exports" mkdir "%ROOT%\exports" >nul 2>nul
if not exist "%ROOT%\backups" mkdir "%ROOT%\backups" >nul 2>nul

set "PYTHON_EXE=%BACKEND_DIR%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo [ERROR] backend venv not found.
  exit /b 1
)
"%PYTHON_EXE%" -c "import fastapi, sqlalchemy, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] backend dependencies unavailable.
  exit /b 1
)

call :pick_port "%BACKEND_PORT%" "backend" BACKEND_PORT
if "%ERRORLEVEL%"=="1" exit /b 1
set "BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%"

echo Starting backend...
set "BACKEND_OUT=%RUNTIME_DIR%\backend.out.log"
set "BACKEND_ERR=%RUNTIME_DIR%\backend.err.log"
powershell -NoProfile -Command "$env:APP_RUN_MODE='desktop-shell'; $env:APP_RUNTIME_MODE='desktop-shell'; $p=Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','%BACKEND_PORT%') -WorkingDirectory '%BACKEND_DIR%' -RedirectStandardOutput '%BACKEND_OUT%' -RedirectStandardError '%BACKEND_ERR%' -PassThru -WindowStyle Hidden; Set-Content -Path '%RUNTIME_DIR%\backend.pid' -Value $p.Id" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] backend start command failed.
  exit /b 1
)

call :wait_url "%BACKEND_URL%/api/health" backend-health
if "%URL_READY%"=="0" (
  echo [ERROR] backend health timeout.
  exit /b 1
)
call :write_listening_pid %BACKEND_PORT% "%RUNTIME_DIR%\backend.pid" backend

call :wait_url "%BACKEND_URL%/" frontend-index
if "%URL_READY%"=="0" (
  echo [ERROR] frontend index timeout.
  exit /b 1
)

echo System started: %BACKEND_URL%/
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0write_runtime_state.ps1" -RuntimeDir "%RUNTIME_DIR%" -BackendPort %BACKEND_PORT% -PrimaryUrl "%BACKEND_URL%/" -Mode "desktop-shell" >nul 2>nul
exit /b 0

:check_port
set "CHECK_PORT=%~1"
set "CHECK_NAME=%~2"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0check_port.ps1" -Port %CHECK_PORT% -Name "%CHECK_NAME%"
if "!ERRORLEVEL!"=="0" goto port_ok
exit /b 1
:port_ok
echo %CHECK_NAME% port %CHECK_PORT% available
exit /b 0

:pick_port
set "PICK_START=%~1"
set "PICK_NAME=%~2"
set "PICK_VAR=%~3"
set "PICK_RESULT="
rem stderr 不再被吞——pick_port.ps1 的"已切换到 X"提示会直接打印给用户
for /f "delims=" %%P in ('powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pick_port.ps1" -StartPort %PICK_START% -Name "%PICK_NAME%"') do (
  set "PICK_RESULT=%%P"
)
if not defined PICK_RESULT (
  echo [错误] %PICK_NAME%端口选择失败,请检查上方 [错误] 提示。
  exit /b 1
)
set "%PICK_VAR%=%PICK_RESULT%"
if not "%PICK_RESULT%"=="%PICK_START%" (
  echo [提示] %PICK_NAME%端口已从 %PICK_START% 自动切换到 %PICK_RESULT%
) else (
  echo %PICK_NAME% port %PICK_RESULT% selected
)
exit /b 0

:try_reuse_runtime_state
set "RUNTIME_READY=0"
if not exist "%RUNTIME_DIR%\ports.json" exit /b 0
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; $state=Get-Content -LiteralPath '%RUNTIME_DIR%\ports.json' -Raw | ConvertFrom-Json; if(-not $state.backend_port){ exit 1 }; $backendUrl=if($state.backend_url){[string]$state.backend_url}else{'http://127.0.0.1:' + [string]$state.backend_port}; $primary=if($state.primary_url){[string]$state.primary_url}else{$backendUrl + '/'}; try { $h=Invoke-WebRequest -Uri ($backendUrl + '/api/health') -UseBasicParsing -TimeoutSec 1; $p=Invoke-WebRequest -Uri $primary -UseBasicParsing -TimeoutSec 1; if($h.StatusCode -ge 200 -and $h.StatusCode -lt 300 -and $p.StatusCode -ge 200 -and $p.StatusCode -lt 500){ Start-Process $primary; exit 0 } } catch { }; exit 1" >nul 2>nul
if "%ERRORLEVEL%"=="0" (
  echo 系统已运行，直接打开。
  set "RUNTIME_READY=1"
)
exit /b 0

:wait_url
set "URL_READY=0"
set "CHECK_URL=%~1"
set "CHECK_NAME=%~2"
powershell -NoProfile -Command "$ok=$false; $deadline=(Get-Date).AddSeconds(30); while((Get-Date) -lt $deadline){ try { $r=Invoke-WebRequest -Uri '%CHECK_URL%' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 500){ $ok=$true; break } } catch { }; Start-Sleep -Milliseconds 250 }; if($ok){ exit 0 } else { exit 1 }" >nul 2>nul
if errorlevel 1 (
  echo [错误] %CHECK_NAME% 超时：%CHECK_URL%
  exit /b 0
)
set "URL_READY=1"
exit /b 0

:write_listening_pid
set "LISTEN_PORT=%~1"
set "PID_FILE=%~2"
set "SERVICE_NAME=%~3"
set "LISTEN_PID="
for /L %%I in (1,1,10) do (
  if not defined LISTEN_PID (
    for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%LISTEN_PORT% .*LISTENING"') do (
      if not defined LISTEN_PID set "LISTEN_PID=%%P"
    )
    if not defined LISTEN_PID powershell -NoProfile -Command "Start-Sleep -Milliseconds 100" >nul 2>nul
  )
)
if defined LISTEN_PID (
  echo %LISTEN_PID%>"%PID_FILE%"
) else (
  echo [警告] 未能识别%SERVICE_NAME%实际监听 PID，停止脚本可能需要手动处理。
)
exit /b 0









