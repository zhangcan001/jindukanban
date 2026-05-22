export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiError extends Error {
  status?: number
  code?: string

  constructor(message: string, status?: number, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    })
  } catch (error) {
    throw normalizeNetworkError(error)
  }

  if (!response.ok) {
    throw await buildApiError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

export async function buildApiError(response: Response): Promise<ApiError> {
  const text = await response.text()
  let message = ''
  let code: string | undefined
  try {
    const parsed = JSON.parse(text)
    const detail = parsed?.detail
    code = typeof detail?.code === 'string' ? detail.code : typeof parsed?.code === 'string' ? parsed.code : undefined
    const parsedMessage = detail?.message ?? detail ?? parsed?.message
    message = typeof parsedMessage === 'string' ? parsedMessage : ''
  } catch (error) {
    if (!(error instanceof SyntaxError)) {
      throw error
    }
  }

  if (code === 'PROJECT_NOT_FOUND' || (response.status === 404 && message === 'Project not found')) {
    code = 'PROJECT_NOT_FOUND'
    message = '当前项目不存在或已被清理。'
    localStorage.removeItem('currentProjectId')
    window.dispatchEvent(new CustomEvent('project-not-found'))
  }

  if (!message) {
    if (response.status === 422) {
      message = '请求参数不正确，请检查字段映射和导入步骤。'
    } else if (response.status >= 500) {
      message = '后端校验异常，请查看日志。'
    } else {
      message = text || `HTTP ${response.status}`
    }
  }

  const friendlyMessages: Record<string, string> = {
    NO_PUBLISHED_BATCH: '当前暂无可导出数据。',
    NO_RECTIFICATIONS_FOR_FILTER: '当前筛选条件下暂无整改项。',
    REPORT_GENERATION_FAILED: '报表生成失败，请查看诊断日志。',
    REPORT_TYPE_NOT_FOUND: '报表类型不存在或未注册。',
    BATCH_FROZEN: '当前批次已冻结，无法覆盖。',
    FIELD_MAPPINGS_EMPTY: '当前数据缺少必要字段，请检查字段映射。',
    SHEET_NOT_SELECTED: '请先选择并解析要导入的 Sheet。',
    PROJECT_ARCHIVED: '当前项目已归档，无法新增导入。',
  }
  if (code && friendlyMessages[code]) {
    message = friendlyMessages[code]
  }

  const literalMessages: Record<string, string> = {
    'Project not found': '当前项目不存在或已被清理。',
    'Published import batch not found': '当前项目暂无已发布批次，请先导入并发布进度数据。',
    'Import batch not found': '导入批次不存在，请刷新后重试。',
    'Only imported batches can be published': '只有已导入成功的批次可以发布。',
    'Inactive batches cannot be published': '当前批次已被替换或停用，无法发布。',
    '当前批次已冻结，不允许覆盖或重新导入。': '当前批次已冻结，无法覆盖。',
    'Progress item not found': '进度明细不存在，请刷新后重试。',
    'Rectification item not found': '整改项不存在，请刷新后重试。',
    'Warning record not found': '预警记录不存在，请刷新后重试。',
    'Warning rule not found': '预警规则不存在，请刷新后重试。',
    'Only xlsx export is supported': '当前仅支持导出 xlsx 文件。',
    'Unsupported delay_level': '滞后等级参数不正确，请重置筛选后重试。',
    'ids required': '请先选择要操作的数据。',
  }
  if (literalMessages[message]) {
    message = literalMessages[message]
  }

  if (/traceback|stack trace|exception/i.test(message)) {
    message = '系统处理失败，请查看诊断日志。'
  }
  if (/failed to fetch|network/i.test(message)) {
    message = '后端服务不可用，请确认系统已启动。'
  }
  if (/REPORT_TYPE_NOT_FOUND/i.test(message)) {
    message = '报表类型不存在或未注册。'
  }
  if (/BATCH_FROZEN/i.test(message)) {
    message = '当前批次已冻结，无法覆盖。'
  }
  if (/FIELD_MAPPINGS_EMPTY|missing required/i.test(message)) {
    message = '当前数据缺少必要字段，请检查字段映射。'
  }
  message = message.replace(/\bNone\b|\bnull\b|\bundefined\b/g, '-')

  return new ApiError(message, response.status, code)
}

export function normalizeNetworkError(error: unknown): ApiError {
  if (error instanceof TypeError && /fetch/i.test(error.message)) {
    return new ApiError('后端服务不可用，请确认系统已启动。')
  }
  if (error instanceof Error) {
    if (/failed to fetch|network/i.test(error.message)) {
      return new ApiError('后端服务不可用，请确认系统已启动。')
    }
    return new ApiError(error.message.replace(/\bNone\b|\bnull\b|\bundefined\b/g, '-'))
  }
  return new ApiError('后端服务不可用，请确认系统已启动。')
}
