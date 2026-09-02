"""SQLAlchemy models. Local-first SQLite, designed to port to PostgreSQL."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class Base(DeclarativeBase):
    pass


class Environment(Base):
    __tablename__ = "environments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Service(Base):
    __tablename__ = "services"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(32), default="service")  # service | database | external
    environment: Mapped[str] = mapped_column(String(64), default="production")
    description: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Dependency(Base):
    __tablename__ = "dependencies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), ForeignKey("services.name"))
    target: Mapped[str] = mapped_column(String(64), ForeignKey("services.name"))
    dep_type: Mapped[str] = mapped_column(String(32), default="depends_on")  # depends_on | uses
    critical: Mapped[bool] = mapped_column(Boolean, default=True)


class TelemetryEvent(Base):
    """Normalized telemetry event - the universal ingestion record."""
    __tablename__ = "telemetry_events"
    id: Mapped[int] = mapped_column(String(40), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    service: Mapped[str] = mapped_column(String(64), index=True)
    environment: Mapped[str] = mapped_column(String(64), default="production")
    severity: Mapped[str] = mapped_column(String(16), default="INFO")  # DEBUG|INFO|WARN|ERROR|CRITICAL
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dedup_hash: Mapped[str] = mapped_column(String(64), index=True)
    raw_source: Mapped[str] = mapped_column(String(16), default="synthetic")


class MetricPoint(Base):
    __tablename__ = "metric_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    service: Mapped[str] = mapped_column(String(64), index=True)
    metric_name: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[float] = mapped_column(Float)
    environment: Mapped[str] = mapped_column(String(64), default="production")


class Deployment(Base):
    __tablename__ = "deployments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    service: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(64), default="ci-system")
    commit: Mapped[str] = mapped_column(String(40), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    environment: Mapped[str] = mapped_column(String(64), default="production")


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="open")  # open|investigating|mitigated|resolved
    severity: Mapped[str] = mapped_column(String(16), default="medium")  # low|medium|high|critical
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    category: Mapped[str] = mapped_column(String(64), default="unknown")
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    affected_services: Mapped[list] = mapped_column(JSON, default=list)
    signals: Mapped[list] = mapped_column(JSON, default=list)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    scenario_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class Hypothesis(Base):
    __tablename__ = "hypotheses"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(32), ForeignKey("incidents.id"), index=True)
    statement: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_for: Mapped[list] = mapped_column(JSON, default=list)
    evidence_against: Mapped[list] = mapped_column(JSON, default=list)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    verdict: Mapped[str] = mapped_column(String(32), default="considered")  # considered|most_likely|rejected


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(32), ForeignKey("incidents.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # metric|log|deployment|topology|analysis
    description: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str] = mapped_column(String(128), default="")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(32), ForeignKey("incidents.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="running")  # running|completed|failed|stopped_limit
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    model: Mapped[str] = mapped_column(String(64), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    llm_request_count: Mapped[int] = mapped_column(Integer, default=0)
    stop_reason: Mapped[str] = mapped_column(String(128), default="")


class ToolCall(Base):
    __tablename__ = "tool_calls"
    id: Mapped[int] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(40), ForeignKey("agent_runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    tool_name: Mapped[str] = mapped_column(String(64))
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    result_status: Mapped[str] = mapped_column(String(16), default="ok")  # ok|error
    duration_ms: Mapped[int] = mapped_column(Float, default=0.0)
    result_summary: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Remediation(Base):
    __tablename__ = "remediations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(32), ForeignKey("incidents.id"), index=True)
    action: Mapped[str] = mapped_column(String(64))
    target_service: Mapped[str] = mapped_column(String(64), default="")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")
    expected_effect: Mapped[str] = mapped_column(Text, default="")
    risk: Mapped[str] = mapped_column(String(16), default="medium")  # low|medium|high
    status: Mapped[str] = mapped_column(String(32), default="proposed")  # proposed|approved|executing|executed|rejected|failed
    approval_state: Mapped[str] = mapped_column(String(32), default="pending")  # pending|approved|rejected
    initiated_by: Mapped[str] = mapped_column(String(64), default="ai-recommender")
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result: Mapped[str] = mapped_column(Text, default="")


class Verification(Base):
    __tablename__ = "verifications"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(32), ForeignKey("incidents.id"), index=True)
    remediation_id: Mapped[str] = mapped_column(String(40), ForeignKey("remediations.id"), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32))  # recovered|partial|not_recovered|unknown
    checked_metrics: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    notes: Mapped[str] = mapped_column(Text, default="")


class Postmortem(Base):
    __tablename__ = "postmortems"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(32), ForeignKey("incidents.id"), index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    content_markdown: Mapped[str] = mapped_column(Text)
    generated_by: Mapped[str] = mapped_column(String(32), default="rule-based")  # rule-based|llm
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(64))
    incident_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    known_root_cause: Mapped[str] = mapped_column(String(128))
    expected_services: Mapped[list] = mapped_column(JSON, default=list)
    predicted_root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    affected_services_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    remediation_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    recovery_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    failed_tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    investigation_duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IngestionStats(Base):
    __tablename__ = "ingestion_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(40), default="")
    received: Mapped[int] = mapped_column(Integer, default=0)
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    malformed: Mapped[int] = mapped_column(Integer, default=0)
    parse_errors: Mapped[list] = mapped_column(JSON, default=list)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
