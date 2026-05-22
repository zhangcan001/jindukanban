export type CalculationProfile = {
  id: number
  project_id: number | null
  name: string
  overall_algorithm: string
  group_algorithm: string
  percent_source: string
  use_weight: boolean
  weight_field?: string | null
  use_value_amount: boolean
  value_field?: string | null
  allow_mixed_unit_sum: boolean
  enable_date_plan_calculation: boolean
  is_default: boolean
  delay_threshold_ahead: number
  delay_threshold_normal: number
  delay_threshold_minor: number
  delay_threshold_major: number
  delay_threshold_overrides?: string | null
  created_at: string
  updated_at: string
}

export type CalculationProfilePayload = Omit<
  CalculationProfile,
  'id' | 'project_id' | 'created_at' | 'updated_at'
>
