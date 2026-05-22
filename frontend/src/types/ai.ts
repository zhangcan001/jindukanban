export type AiConfigRead = {
  enabled: boolean
  api_base_url?: string | null
  api_key_set: boolean
  model?: string | null
  timeout_seconds: number
  last_test_result?: string | null
  last_test_at?: string | null
  last_call_at?: string | null
}

export type AiConfigPayload = {
  enabled: boolean
  api_base_url?: string | null
  api_key?: string | null
  model?: string | null
  timeout_seconds: number
}

export type AiInsightResponse = {
  enabled: boolean
  generated_text: string
  fallback_text: string
  source: 'ai' | 'rule_fallback'
  error_message?: string | null
}

export type AiPromptTemplate = {
  id: number
  project_id?: number | null
  name: string
  code: string
  description?: string | null
  prompt_template: string
  is_builtin: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export type AiCallLog = {
  id: number
  project_id?: number | null
  batch_id?: number | null
  mode: string
  model?: string | null
  source: 'ai' | 'rule_fallback'
  success: boolean
  error_message?: string | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  input_summary_length?: number | null
  output_length?: number | null
  duration_ms: number
  created_at: string
}
