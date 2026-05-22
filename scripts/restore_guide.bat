@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"

echo ========================================
echo 工程进度看板 v5.0-desktop-shell 恢复备份说明
echo ========================================
echo.
echo 恢复操作会覆盖当前数据，请谨慎操作。
echo 本脚本只显示说明，不会自动复制或覆盖任何文件。
echo.
echo 建议步骤：
echo 1. 先运行 scripts\stop.bat 关闭系统。
echo 2. 先运行 scripts\backup.bat 备份当前数据库、上传文件和导出报表。
echo 3. 从目标备份目录中找到数据库文件 progress_dashboard.db。
echo 4. 将备份中的数据库文件复制回：
if exist "%ROOT%\frontend_dist\index.html" (
  echo    %ROOT%\data\progress_dashboard.db
) else (
  echo    %ROOT%\backend\progress_dashboard.db
)
echo 5. 将备份中的 uploads 目录复制回：
if exist "%ROOT%\frontend_dist\index.html" (
  echo    %ROOT%\uploads
) else (
  echo    %ROOT%\backend\uploads
)
echo 6. 如需恢复导出报表，将备份中的 reports 目录复制回：
if exist "%ROOT%\frontend_dist\index.html" (
  echo    %ROOT%\exports
) else (
  echo    %ROOT%\backend\reports
)
echo 7. 运行 scripts\start.bat 重新启动系统。
echo.
echo 当前备份根目录：
echo %ROOT%\backups
echo.
pause
exit /b 0










