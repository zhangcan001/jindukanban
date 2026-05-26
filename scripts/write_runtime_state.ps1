param(
  [Parameter(Mandatory = $true)]
  [string]$RuntimeDir,
  [Parameter(Mandatory = $true)]
  [int]$BackendPort,
  [int]$FrontendPort = 0,
  [Parameter(Mandatory = $true)]
  [string]$PrimaryUrl,
  [string]$Mode = "source"
)

# 把当前活动端口持久化到 .runtime/ports.json 和 last_url.txt:
# - stop.bat 据此知道要关哪个端口(原来 hardcode 8000/5173 会漏掉自动切换后的端口)
# - 桌面快捷方式、外部脚本、用户截图 bug 时都能从 last_url.txt 一行拿到当前地址
if (-not (Test-Path -LiteralPath $RuntimeDir)) {
  New-Item -ItemType Directory -Path $RuntimeDir | Out-Null
}

$state = [ordered]@{
  backend_port  = $BackendPort
  frontend_port = if ($FrontendPort -gt 0) { $FrontendPort } else { $null }
  backend_url   = "http://127.0.0.1:$BackendPort"
  frontend_url  = if ($FrontendPort -gt 0) { "http://127.0.0.1:$FrontendPort" } else { "http://127.0.0.1:$BackendPort" }
  primary_url   = $PrimaryUrl
  mode          = $Mode
  started_at    = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
}

$json = ($state | ConvertTo-Json -Depth 3)
Set-Content -LiteralPath (Join-Path $RuntimeDir "ports.json") -Value $json -Encoding UTF8
Set-Content -LiteralPath (Join-Path $RuntimeDir "last_url.txt") -Value $PrimaryUrl -Encoding UTF8
