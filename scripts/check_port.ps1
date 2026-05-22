param(
  [Parameter(Mandatory = $true)]
  [int]$Port,
  [string]$Name = "服务"
)

$connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
if ($connection) {
  Write-Host ("[错误] {0}端口 {1} 已被占用，且不是本次启动的进程。" -f $Name, $Port)
  Write-Host "为避免误杀其他程序，系统不会自动关闭该进程。"
  Write-Host "请手动关闭占用程序，或使用临时端口启动。"
  Write-Host "示例："
  Write-Host "set BACKEND_PORT=8028"
  Write-Host "set FRONTEND_PORT=5228"
  Write-Host "start.bat"
  exit 1
}
exit 0
