param(
  [Parameter(Mandatory = $true)][string]$Target,
  [Parameter(Mandatory = $true)][string]$Version,
  [Parameter(Mandatory = $true)][string]$Root
)

$pythonVersion = (python --version 2>&1) -join " "
$nodeVersion = (node --version 2>&1) -join " "
$lines = @(
  "版本：$Version",
  "当前推荐版本：$Version",
  "生成时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
  "包类型：portable",
  "源项目路径：$Root",
  "Python 版本：$pythonVersion",
  "Node 版本：$nodeVersion",
  "是否包含 PDF 导出能力：是",
  "是否包含 AI 辅助能力：是",
  "是否包含备份恢复能力：是",
  "是否包含示例数据：是",
  "示例数据目录：sample_data",
  "Dashboard V2 默认看板：是",
  "full_auto_check 全功能自动验收：是",
  "quick_check 快速验收：是",
  "数据目录：data",
  "上传目录：uploads",
  "导出目录：exports",
  "备份目录：backups",
  "pytest 结果：请查看构建前测试记录",
  "npm build 结果：frontend/dist 已存在并已复制"
)

$output = Join-Path $Target "package_info.txt"
$lines | Set-Content -Path $output -Encoding UTF8
