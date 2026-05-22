param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$SamplePath = "samples\sample_progress_a.csv",
  [string]$DownloadDir = ".runtime\rc-smoke"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if (-not (Test-Path -LiteralPath $SamplePath)) {
  $SamplePath = Join-Path $root $SamplePath
}
$SamplePath = (Resolve-Path -LiteralPath $SamplePath).Path
$DownloadDir = Join-Path $root $DownloadDir
New-Item -ItemType Directory -Force -Path $DownloadDir | Out-Null

function Invoke-Json {
  param(
    [string]$Method,
    [string]$Path,
    [object]$Body = $null
  )
  $uri = "$BaseUrl$Path"
  if ($null -eq $Body) {
    $response = Invoke-WebRequest -Method $Method -Uri $uri -UseBasicParsing
  } else {
    $json = $Body | ConvertTo-Json -Depth 20
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    $response = Invoke-WebRequest -Method $Method -Uri $uri -ContentType "application/json; charset=utf-8" -Body $bytes -UseBasicParsing
  }
  $content = [System.Text.Encoding]::UTF8.GetString($response.RawContentStream.ToArray())
  return $content | ConvertFrom-Json
}

function Assert($Condition, $Message) {
  if (-not $Condition) {
    throw $Message
  }
}

$health = Invoke-Json GET "/api/health"
Assert ($health.status -eq "ok") "health check failed"

$project = Invoke-Json POST "/api/projects" @{ name = "v5.0-desktop-shell 整改闭环冒烟项目 $(Get-Date -Format HHmmss)"; project_type = "测试" }
$projectId = $project.id

$uploadJson = & curl.exe -sS -X POST "$BaseUrl/api/projects/$projectId/imports/upload" -F "data_date=2026-05-13" -F "file=@$SamplePath"
if ($LASTEXITCODE -ne 0) {
  throw "upload request failed"
}
$upload = $uploadJson | ConvertFrom-Json
$batchId = $upload.batch.id
Assert ($upload.sheets -contains "CSV") "upload did not return CSV sheet"

$parse = Invoke-Json POST "/api/imports/$batchId/parse" @{
  sheet_name = "CSV"
  header_row_index = 1
  data_start_row_index = 2
}
Assert ($parse.batch.row_count -ge 1) "parse returned no rows"
$mappings = @($parse.columns | ForEach-Object {
  @{
    excel_column_name = $_.name
    system_field_name = $_.recommended_field
    field_type = $_.field_type
    is_dimension = $_.is_dimension
    is_metric = $_.is_metric
    save_to_extra = $_.save_to_extra
  }
})

$mapping = Invoke-Json POST "/api/imports/$batchId/mapping/validate" @{ field_mappings = $mappings }
Assert ($mapping.valid -eq $true) "mapping validation failed"

$validation = Invoke-Json POST "/api/imports/$batchId/validate" @{ field_mappings = $mappings }
Assert ($validation.valid -eq $true) "import validation failed"

$confirm = Invoke-Json POST "/api/imports/$batchId/confirm" @{
  save_as_template = $true
  template_name = "rc-smoke-template"
  data_date = "2026-05-14"
  import_strategy = "new_batch"
  field_mappings = $mappings
}
Assert ($confirm.status -eq "imported") "confirm import failed"

$publish = Invoke-Json POST "/api/imports/$batchId/publish"
Assert ($publish.status -eq "published") "publish failed"

$overview = Invoke-Json GET "/api/projects/$projectId/analytics/overview?batch_id=$batchId"
$floor = Invoke-Json GET "/api/projects/$projectId/analytics/group-by?dimension=floor&batch_id=$batchId"
$buildingFloor = Invoke-Json GET "/api/projects/$projectId/analytics/building-floor?batch_id=$batchId"
$insight = Invoke-Json GET "/api/projects/$projectId/analytics/insight?batch_id=$batchId"
Assert ($overview.item_count -ge 1) "dashboard overview empty"
Assert ($floor.rows.Count -ge 1) "floor statistics empty"
Assert ($buildingFloor.items.Count -ge 1) "building floor statistics empty"
Assert ($insight.overview_summary) "progress insight empty"

$runWarnings = Invoke-Json POST "/api/projects/$projectId/warnings/run?batch_id=$batchId"
$warnings = Invoke-Json GET "/api/projects/$projectId/warnings?batch_id=$batchId"
Assert ($runWarnings.generated_count -ge 1) "warnings were not generated"
Assert ($warnings.Count -ge 1) "warning list empty"
$locatedWarning = $warnings | Where-Object { $_.building -and $_.floor -and $_.discipline -and $_.task_name } | Select-Object -First 1
Assert ($null -ne $locatedWarning) "warning location fields missing"
Assert ($locatedWarning.level_label -notin @("critical", "warning", "info")) "warning level is not localized"
Assert ($locatedWarning.status_label -in @("未处理", "已处理", "已忽略")) "warning status is not localized"
Assert ($locatedWarning.warning_message -match $locatedWarning.building) "warning message missing building"
Assert ($locatedWarning.warning_message -match $locatedWarning.floor) "warning message missing floor"
Assert ($locatedWarning.warning_message -match $locatedWarning.task_name) "warning message missing task"
Assert ($locatedWarning.warning_message -match "\d+\.\d%|\d+\.\d 个百分点") "warning message percent precision not found"

$buildingFilter = Invoke-Json GET "/api/projects/$projectId/warnings?batch_id=$batchId&building=$([uri]::EscapeDataString($locatedWarning.building))"
$floorFilter = Invoke-Json GET "/api/projects/$projectId/warnings?batch_id=$batchId&floor=$([uri]::EscapeDataString($locatedWarning.floor))"
Assert ($buildingFilter.Count -ge 1) "building warning filter failed"
Assert ($floorFilter.Count -ge 1) "floor warning filter failed"

$delayed = Invoke-Json GET "/api/projects/$projectId/analytics/delayed-ranking?batch_id=$batchId"
Assert ($delayed.rows.Count -ge 1) "delayed ranking empty"
$delayedSource = $delayed.rows | Select-Object -First 1
$fromDelayed = Invoke-Json POST "/api/projects/$projectId/rectifications/from-progress-items" @{
  batch_id = $batchId
  progress_item_id = $delayedSource.progress_item_id
}
Assert ($fromDelayed.created -eq $true) "rectification from delayed item not created"

$fromWarning = Invoke-Json POST "/api/projects/$projectId/rectifications/from-warnings" @{ warning_record_id = $locatedWarning.id }
Assert ($fromWarning.created -eq $true) "rectification from warning not created"

$rectificationIds = @($fromDelayed.item.id, $fromWarning.item.id)
$overdueDate = (Get-Date).AddDays(-1).ToString("yyyy-MM-dd")
$batchUpdate = Invoke-Json POST "/api/projects/$projectId/rectifications/batch-update" @{
  ids = $rectificationIds
  status = "in_progress"
  responsible_person = "RC责任人"
  responsible_unit = "RC责任单位"
  planned_finish_date = $overdueDate
  remark = "v5.0-desktop-shell 批量整改回归"
}
Assert ($batchUpdate.updated_count -eq $rectificationIds.Count) "batch update failed"

foreach ($targetStatus in @("completed", "closed", "ignored")) {
  $created = Invoke-Json POST "/api/projects/$projectId/rectifications" @{
    batch_id = $batchId
    source_type = "manual"
    task_name = "RC批量状态-$targetStatus"
    status = "open"
  }
  $updated = Invoke-Json POST "/api/projects/$projectId/rectifications/batch-update" @{
    ids = @($created.id)
    status = $targetStatus
  }
  Assert ($updated.updated_count -eq 1) "batch status $targetStatus failed"
}

$rectifications = Invoke-Json GET "/api/projects/$projectId/rectifications?page=1&page_size=1&sort_by=planned_finish_date&sort_order=asc"
Assert (($rectifications.total -ge 2) -and ($rectifications.items.Count -eq 1)) "rectification pagination failed"
$overdue = Invoke-Json GET "/api/projects/$projectId/rectifications?batch_id=$batchId&overdue=true"
Assert ($overdue.total -ge 2) "overdue filter failed"
Assert (($overdue.items | Where-Object { -not $_.is_overdue }).Count -eq 0) "overdue flag mismatch"
$personFilter = Invoke-Json GET "/api/projects/$projectId/rectifications?responsible_person=$([uri]::EscapeDataString('RC责任人'))"
$unitFilter = Invoke-Json GET "/api/projects/$projectId/rectifications?responsible_unit=$([uri]::EscapeDataString('RC责任单位'))"
Assert ($personFilter.total -ge 2) "responsible person filter failed"
Assert ($unitFilter.total -ge 2) "responsible unit filter failed"
$summary = Invoke-Json GET "/api/projects/$projectId/rectifications/summary?batch_id=$batchId"
Assert (($summary.total -ge 2) -and ($summary.in_progress -ge 2) -and ($summary.overdue -ge 2)) "rectification summary failed"
$logs = Invoke-Json GET "/api/projects/$projectId/rectifications/$($rectificationIds[0])/logs"
$batchLogMatches = @($logs | Where-Object { $_.action -eq "status_change" -and $_.from_status -eq "open" -and $_.to_status -eq "in_progress" })
Assert ($batchLogMatches.Count -ge 1) "operation log missing batch update"

$downloads = @{
  dashboard = Join-Path $DownloadDir "dashboard.xlsx"
  weekly = Join-Path $DownloadDir "weekly.docx"
  rectification = Join-Path $DownloadDir "rectification.xlsx"
  rectification_tracking = Join-Path $DownloadDir "rectification-tracking.xlsx"
  warnings = Join-Path $DownloadDir "warnings.xlsx"
}
Invoke-WebRequest -Uri "$BaseUrl/api/projects/$projectId/reports/dashboard-export?batch_id=$batchId" -OutFile $downloads.dashboard | Out-Null
Invoke-WebRequest -Uri "$BaseUrl/api/projects/$projectId/reports/weekly-word?batch_id=$batchId" -OutFile $downloads.weekly | Out-Null
Invoke-WebRequest -Uri "$BaseUrl/api/projects/$projectId/reports/delay-rectification-export?batch_id=$batchId" -OutFile $downloads.rectification | Out-Null
Invoke-WebRequest -Uri "$BaseUrl/api/projects/$projectId/rectifications/export?batch_id=$batchId" -OutFile $downloads.rectification_tracking | Out-Null
Invoke-WebRequest -Uri "$BaseUrl/api/projects/$projectId/warnings/export?batch_id=$batchId" -OutFile $downloads.warnings | Out-Null
foreach ($path in $downloads.Values) {
  Assert ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path).Length -gt 0)) "download failed: $path"
}

$exports = Invoke-Json GET "/api/projects/$projectId/reports/exports"
Assert ($exports.Count -ge 3) "report history missing exports"

$maintenance = Invoke-Json GET "/api/maintenance/runtime-status"
Assert ($maintenance.portable_mode -eq $true) "runtime status is not portable"
Assert ($maintenance.database_path -match "工程进度管理系统-v4\.0-installer-lite\\app\\data\\progress_dashboard\.db") "database path is not installer-lite data"
Assert ($maintenance.export_dir -match "工程进度管理系统-v4\.0-installer-lite\\app\\exports") "export path is not installer-lite exports"

$result = [ordered]@{
  project_id = $projectId
  batch_id = $batchId
  warning_count = $warnings.Count
  rectification_summary = $summary
  exports_count = $exports.Count
  building_filter_count = $buildingFilter.Count
  floor_filter_count = $floorFilter.Count
  downloads = $downloads
  database_path = $maintenance.database_path
  upload_dir = $maintenance.upload_dir
  export_dir = $maintenance.export_dir
  backup_dir = $maintenance.backup_dir
}
$result | ConvertTo-Json -Depth 8





