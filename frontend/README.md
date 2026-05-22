# progress-dashboard frontend

Vue 3 frontend for the engineering progress dashboard MVP.

## Start

```powershell
cd frontend
npm install
npm run dev
```

The home page calls:

```text
http://localhost:8000/api/health
```

Set a different backend URL with `VITE_API_BASE_URL` if needed.

The import mapping page now supports validation, data quality scoring, formal import confirmation, and publishing imported batches to the later dashboard scope.

Analytics API helpers are available in `src/api/analytics.ts` for the dashboard phase.

The project dashboard is available at:

```text
/projects/{project_id}/dashboard
```

It uses only published and active batches returned by the analytics APIs.

The progress item correction page is available at:

```text
/projects/{project_id}/progress-items
```

The warning center is available at:

```text
/projects/{project_id}/warnings
```

The report center is available at:

```text
/projects/{project_id}/reports
```
