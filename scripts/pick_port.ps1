param(
  [Parameter(Mandatory = $true)]
  [int]$StartPort,
  [string]$Name = "服务",
  [int]$MaxAttempts = 10
)

for ($offset = 0; $offset -lt $MaxAttempts; $offset++) {
  $candidate = $StartPort + $offset
  $connection = Get-NetTCPConnection -State Listen -LocalPort $candidate -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $connection) {
    if ($offset -gt 0) {
      Write-Host ("[提示] {0}默认端口 {1} 被占用，自动切换到 {2}。" -f $Name, $StartPort, $candidate)
    }
    Write-Output $candidate
    exit 0
  }
}

Write-Host ("[错误] {0}在 {1} .. {2} 范围内未找到可用端口。" -f $Name, $StartPort, ($StartPort + $MaxAttempts - 1))
exit 1
