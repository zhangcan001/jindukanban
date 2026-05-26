param(
  [Parameter(Mandatory = $true)]
  [int]$StartPort,
  [string]$Name = "服务",
  [int]$MaxAttempts = 10
)

# 注意:端口号通过 stdout (Write-Output) 输出,供 start.bat 的 for /f 解析;
# 切换提示用 [Console]::Error.WriteLine 写到 stderr,这样:
# 1. for /f 不会把它误当成端口号;
# 2. start.bat 取消 2>nul 后用户能看到"已切换到 800X"的提示。
for ($offset = 0; $offset -lt $MaxAttempts; $offset++) {
  $candidate = $StartPort + $offset
  $connection = Get-NetTCPConnection -State Listen -LocalPort $candidate -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $connection) {
    if ($offset -gt 0) {
      $msg = "[提示] {0}默认端口 {1} 被占用,已自动切换到 {2}。" -f $Name, $StartPort, $candidate
      [Console]::Error.WriteLine($msg)
    }
    Write-Output $candidate
    exit 0
  }
}

$msg = "[错误] {0}在 {1} .. {2} 范围内未找到可用端口。" -f $Name, $StartPort, ($StartPort + $MaxAttempts - 1)
[Console]::Error.WriteLine($msg)
exit 1
