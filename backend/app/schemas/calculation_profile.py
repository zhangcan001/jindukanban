from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CalculationProfileBase(BaseModel):
    name: str
    overall_algorithm: str = "avg_percent"
    group_algorithm: str = "avg_percent"
    percent_source: str = "provided_percent_first"
    use_weight: bool = False
    weight_field: str | None = None
    use_value_amount: bool = False
    value_field: str | None = None
    allow_mixed_unit_sum: bool = False
    enable_date_plan_calculation: bool = True
    is_default: bool = False
    delay_threshold_ahead: float = 5.0
    delay_threshold_normal: float = -5.0
    delay_threshold_minor: float = -10.0
    delay_threshold_major: float = -20.0
    delay_threshold_overrides: str | None = None

    @field_validator("delay_threshold_overrides")
    @classmethod
    def _validate_overrides_json(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        import json

        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"delay_threshold_overrides 必须是合法 JSON 字符串: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("delay_threshold_overrides 必须是 JSON 对象 (dict)")
        return value


class CalculationProfileCreate(CalculationProfileBase):
    pass


class CalculationProfileUpdate(BaseModel):
    name: str | None = None
    overall_algorithm: str | None = None
    group_algorithm: str | None = None
    percent_source: str | None = None
    use_weight: bool | None = None
    weight_field: str | None = None
    use_value_amount: bool | None = None
    value_field: str | None = None
    allow_mixed_unit_sum: bool | None = None
    enable_date_plan_calculation: bool | None = None
    is_default: bool | None = None
    delay_threshold_ahead: float | None = None
    delay_threshold_normal: float | None = None
    delay_threshold_minor: float | None = None
    delay_threshold_major: float | None = None
    delay_threshold_overrides: str | None = Field(default=None)

    @field_validator("delay_threshold_overrides")
    @classmethod
    def _validate_overrides_json(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        import json

        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"delay_threshold_overrides 必须是合法 JSON 字符串: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("delay_threshold_overrides 必须是 JSON 对象 (dict)")
        return value


class CalculationProfileRead(CalculationProfileBase):
    id: int
    project_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
