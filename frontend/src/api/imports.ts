import { apiBaseUrl, buildApiError, normalizeNetworkError, request } from './http'
import type {
  FieldMapping,
  FieldDiagnostics,
  ImportConfirmRequest,
  ImportConfirmResponse,
  ImportParseRequest,
  ImportParseResponse,
  ImportPublishResponse,
  ImportUploadResponse,
  ImportValidationResponse,
  MappingValidationResponse,
  ImportBatch,
  MultiSheetConfirmRequest,
  MultiSheetConfirmResponse,
  MultiSheetParseRequest,
  MultiSheetParseResponse,
  MultiSheetPublishResponse,
  MultiSheetValidationResponse,
  MultiSheetValidationSheetRequest,
} from '../types/import'

export async function uploadImportFile(projectId: number, file: File, dataDate?: string | null) {
  const formData = new FormData()
  formData.append('file', file)
  if (dataDate) {
    formData.append('data_date', dataDate)
  }

  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}/api/projects/${projectId}/imports/upload`, {
      method: 'POST',
      body: formData,
    })
  } catch (error) {
    throw normalizeNetworkError(error)
  }

  if (!response.ok) {
    throw await buildApiError(response)
  }

  return response.json() as Promise<ImportUploadResponse>
}

export function listProjectImports(projectId: number) {
  return request<ImportBatch[]>(`/api/projects/${projectId}/imports`)
}

export function parseImportBatch(batchId: number, payload: ImportParseRequest) {
  return request<ImportParseResponse>(`/api/imports/${batchId}/parse`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function validateFieldMappings(batchId: number, fieldMappings: FieldMapping[]) {
  return request<MappingValidationResponse>(`/api/imports/${batchId}/mapping/validate`, {
    method: 'POST',
    body: JSON.stringify({ field_mappings: fieldMappings }),
  })
}

export function getFieldDiagnostics(batchId: number) {
  return request<FieldDiagnostics>(`/api/imports/${batchId}/field-diagnostics`)
}

export function validateImportBatch(batchId: number, fieldMappings: FieldMapping[]) {
  return request<ImportValidationResponse>(`/api/imports/${batchId}/validate`, {
    method: 'POST',
    body: JSON.stringify({ field_mappings: fieldMappings }),
  })
}

export function confirmImportBatch(batchId: number, payload: ImportConfirmRequest) {
  return request<ImportConfirmResponse>(`/api/imports/${batchId}/confirm`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function publishImportBatch(batchId: number) {
  return request<ImportPublishResponse>(`/api/imports/${batchId}/publish`, {
    method: 'POST',
  })
}

export function parseMultipleSheets(fileId: number, payload: MultiSheetParseRequest) {
  return request<MultiSheetParseResponse>(`/api/imports/${fileId}/parse-multiple-sheets`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function validateMultipleSheets(sheets: MultiSheetValidationSheetRequest[]) {
  return request<MultiSheetValidationResponse>('/api/imports/validate-multiple-sheets', {
    method: 'POST',
    body: JSON.stringify({ sheets }),
  })
}

export function confirmMultipleSheets(payload: MultiSheetConfirmRequest) {
  return request<MultiSheetConfirmResponse>('/api/imports/confirm-multiple-sheets', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function publishMultipleSheets(batchIds: number[]) {
  return request<MultiSheetPublishResponse>('/api/imports/publish-multiple-sheets', {
    method: 'POST',
    body: JSON.stringify(batchIds),
  })
}

export function freezeImportBatch(batchId: number, freezeRemark?: string | null) {
  return request<ImportBatch>(`/api/imports/${batchId}/freeze`, {
    method: 'POST',
    body: JSON.stringify({ freeze_remark: freezeRemark ?? null }),
  })
}

export function unfreezeImportBatch(batchId: number) {
  return request<ImportBatch>(`/api/imports/${batchId}/unfreeze`, {
    method: 'POST',
  })
}

export async function downloadImportErrorReport(batchId: number): Promise<{ blob: Blob; filename: string }> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}/api/imports/${batchId}/error-report`, {
      method: 'GET',
    })
  } catch (error) {
    throw normalizeNetworkError(error)
  }
  if (!response.ok) {
    throw await buildApiError(response)
  }
  const blob = await response.blob()
  const filename = extractFilename(response.headers.get('content-disposition')) || `error-report-${batchId}.xlsx`
  return { blob, filename }
}

function extractFilename(disposition: string | null): string | null {
  if (!disposition) return null
  const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8) {
    try {
      return decodeURIComponent(utf8[1])
    } catch {
      // fall through
    }
  }
  const fallback = disposition.match(/filename="?([^";]+)"?/i)
  return fallback ? fallback[1] : null
}
