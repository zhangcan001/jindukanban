from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AiConfig(BaseModel):
    enabled: bool = False
    api_base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout_seconds: int = 20


class AiConfigRead(BaseModel):
    enabled: bool = False
    api_base_url: str | None = None
    api_key_set: bool = False
    model: str | None = None
    timeout_seconds: int = 20
    last_test_result: str | None = None
    last_test_at: datetime | None = None
    last_call_at: datetime | None = None


class AiInsightRequest(BaseModel):
    batch_id: int | None = None
    calculation_profile_id: int | None = None
    baseline_plan_id: int | None = None
    building: str | None = None
    mode: str = Field(default="dashboard_summary")


class AiInsightResponse(BaseModel):
    enabled: bool
    generated_text: str
    fallback_text: str
    source: str
    error_message: str | None = None


class AiConnectionTestRequest(BaseModel):
    api_base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    timeout_seconds: int = 20


class AiConnectionTestResponse(BaseModel):
    success: bool
    message: str
    tested_at: datetime | None = None


class AiPromptTemplateBase(BaseModel):
    name: str
    code: str
    description: str | None = None
    prompt_template: str
    is_active: bool = True


class AiPromptTemplateCreate(AiPromptTemplateBase):
    project_id: int | None = None


class AiPromptTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    prompt_template: str | None = None
    is_active: bool | None = None


class AiPromptTemplateRead(AiPromptTemplateBase):
    id: int
    project_id: int | None = None
    is_builtin: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AiCallLogRead(BaseModel):
    id: int
    project_id: int | None = None
    batch_id: int | None = None
    mode: str
    model: str | None = None
    source: str
    success: bool
    error_message: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    input_summary_length: int | None = None
    output_length: int | None = None
    duration_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}
