"""Pydantic schemas for API request/response typing."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TelemetryEventIn(BaseModel):
    timestamp: str | datetime | int | float
    service: str
    environment: str = "production"
    severity: str = "INFO"
    event_type: str = "generic"
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None


class IngestResponse(BaseModel):
    received: int
    accepted: int
    duplicates: int
    malformed: int
    parse_errors: list[str]


class ApprovalRequest(BaseModel):
    approver: str = "human-operator"
    approved: bool = True


class ExecuteRequest(BaseModel):
    remediation_id: str


class SettingsOut(BaseModel):
    llm_provider: str
    llm_model: str
    llm_enabled: bool
    remediation_mode: str
    demo_mode: bool
    agent_max_tool_calls: int


class InvestigationOut(BaseModel):
    run_id: str
    incident_id: str
    status: str
    hypotheses: list[dict]
    root_cause: str | None
    root_cause_confidence: float
    recommended_action: dict | None
    summary: str
    stop_reason: str
    input_tokens: int
    output_tokens: int
    llm_request_count: int
    tool_calls: list[dict]
