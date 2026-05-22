param(
  [int]$DaysToKeep = 30,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$cutoff = (Get-Date).AddDays(-$DaysToKeep)

$patterns = @(
  @{ Path = (Join-Path $root "backend"); Filter = "uvicorn-*.log" },
  @{ Path = (Join-Path $root "backend"); Filter = "*.out.log" },
  @{ Path = (Join-Path $root "backend"); Filter = "*.err.log" },
  @{ Path = (Join-Path $root "frontend"); Filter = "vite-*.log" },
  @{ Path = (Join-Path $root "frontend"); Filter = "vite.*.log" },
  @{ Path = (Join-Path $root ".runtime"); Filter = "*.log" },
  @{ Path = (Join-Path $root "logs"); Filter = "*.log" }
)

$totalRemoved = 0
$totalBytes = 0L

foreach ($p in $patterns) {
  if (-not (Test-Path -LiteralPath $p.Path)) { continue }
  $files = Get-ChildItem -LiteralPath $p.Path -Filter $p.Filter -File -ErrorAction SilentlyContinue
  foreach ($f in $files) {
    if ($f.LastWriteTime -lt $cutoff) {
      $totalRemoved += 1
      $totalBytes += $f.Length
      if ($DryRun) {
        Write-Host ("[dry-run] would delete: {0} ({1:N0} bytes, last write {2:yyyy-MM-dd})" -f $f.FullName, $f.Length, $f.LastWriteTime)
      } else {
        Remove-Item -LiteralPath $f.FullName -Force
        Write-Host ("[deleted] {0}" -f $f.FullName)
      }
    }
  }
}

$mb = [math]::Round($totalBytes / 1MB, 2)
if ($DryRun) {
  Write-Host ("[summary] would prune {0} files, {1} MB (older than {2} days)" -f $totalRemoved, $mb, $DaysToKeep)
} else {
  Write-Host ("[summary] pruned {0} files, {1} MB (older than {2} days)" -f $totalRemoved, $mb, $DaysToKeep)
}
