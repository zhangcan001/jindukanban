# progress-dashboard backend

FastAPI backend for the engineering progress dashboard MVP.

## Start

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Health check:

```text
GET http://localhost:8000/api/health
```

## Import confirmation

After upload, parse, mapping, and validation, confirm a batch with:

```text
POST /api/imports/{batch_id}/confirm
```

The endpoint creates or matches `progress_task`, writes `progress_item`, stores `raw_import_row`, optionally saves a mapping template, records `audit_log`, and leaves the batch in `imported` status.

Publish an imported batch with:

```text
POST /api/imports/{batch_id}/publish
```

Only `imported` and active batches can be published. Later analytics should use `status = published` and `is_active = true` as the default scope.

Formal import also runs `progress_calculator` before writing `progress_item`, calculating actual/planned percent, time planned percent, remaining quantity, deviation, status, and current-period increment with the selected or default calculation profile and baseline plan.

Analytics endpoints:

```text
GET /api/projects/{project_id}/analytics/fields
GET /api/projects/{project_id}/analytics/overview
GET /api/projects/{project_id}/analytics/group-by
GET /api/projects/{project_id}/analytics/plan-vs-actual
GET /api/projects/{project_id}/analytics/delayed-ranking
GET /api/projects/{project_id}/analytics/trend
GET /api/projects/{project_id}/analytics/data-quality
```

They default to `published + is_active` batches and return unit-mixed warnings where relevant.

Manual progress item correction endpoints:

```text
GET /api/projects/{project_id}/progress-items
PUT /api/progress-items/{item_id}
GET /api/progress-items/{item_id}/edit-history
```

Updates require a reason, save `progress_item_edit_history`, mark the item as manually edited, and recalculate progress fields.

Warning endpoints:

```text
GET /api/projects/{project_id}/warning-rules
POST /api/projects/{project_id}/warnings/run
GET /api/projects/{project_id}/warnings
```

Built-in rules cover consecutive delay, serious delay, no growth, zero current-period quantity, near planned finish with low progress, and low data quality.

Report endpoints:

```text
GET /api/projects/{project_id}/reports/overview
GET /api/projects/{project_id}/reports/delayed-ranking
GET /api/projects/{project_id}/reports/discipline-summary
GET /api/projects/{project_id}/reports/progress-items
GET /api/projects/{project_id}/reports/exports
```

Exports are `.xlsx` files generated with openpyxl and saved to `report_export_record`.

## Tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
```

The current tests use an isolated `test_progress_dashboard.db` and cover health check, import validation and normalization, abnormal sample regression, the CSV import/publish API flow, progress calculation, warning generation, and report export.
