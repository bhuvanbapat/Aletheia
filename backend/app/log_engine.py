"""Log engine: structured queries with filtering by service/severity/time/type/incident."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import TelemetryEvent


def query_logs(
    db: Session,
    service: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    search: str | None = None,
    trace_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[TelemetryEvent]:
    stmt = select(TelemetryEvent)
    conditions = []
    if service:
        conditions.append(TelemetryEvent.service == service)
    if severity:
        conditions.append(TelemetryEvent.severity == severity)
    if event_type:
        conditions.append(TelemetryEvent.event_type == event_type)
    if start:
        conditions.append(TelemetryEvent.timestamp >= start)
    if end:
        conditions.append(TelemetryEvent.timestamp <= end)
    if trace_id:
        conditions.append(TelemetryEvent.trace_id == trace_id)
    if search:
        conditions.append(TelemetryEvent.message.ilike(f"%{search}%"))
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(TelemetryEvent.timestamp.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


def count_logs(
    db: Session,
    service: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    search: str | None = None,
) -> int:
    stmt = select(func_count(TelemetryEvent.id))
    conditions = []
    if service:
        conditions.append(TelemetryEvent.service == service)
    if severity:
        conditions.append(TelemetryEvent.severity == severity)
    if event_type:
        conditions.append(TelemetryEvent.event_type == event_type)
    if start:
        conditions.append(TelemetryEvent.timestamp >= start)
    if end:
        conditions.append(TelemetryEvent.timestamp <= end)
    if search:
        conditions.append(TelemetryEvent.message.ilike(f"%{search}%"))
    if conditions:
        stmt = stmt.where(and_(*conditions))
    return int(db.execute(stmt).scalar() or 0)


def func_count(*args):  # tiny shim to avoid importing func at module top twice
    from sqlalchemy import func

    return func.count(*args)


def event_to_dict(e: TelemetryEvent) -> dict:
    return {
        "id": e.id,
        "timestamp": e.timestamp,
        "service": e.service,
        "environment": e.environment,
        "severity": e.severity,
        "event_type": e.event_type,
        "message": e.message,
        "metadata": e.metadata_json or {},
        "trace_id": e.trace_id,
        "raw_source": e.raw_source,
    }


def log_stats(db: Session, window_minutes: int = 60) -> dict:
    """Counts by severity for the recent window - used by the overview page."""
    from datetime import timedelta

    from sqlalchemy import func

    latest = db.execute(select(func.max(TelemetryEvent.timestamp))).scalar()
    stmt = select(TelemetryEvent.severity, func.count(TelemetryEvent.id))
    if latest is not None:
        stmt = stmt.where(TelemetryEvent.timestamp >= latest - timedelta(minutes=window_minutes))
    stmt = stmt.group_by(TelemetryEvent.severity)
    rows = db.execute(stmt).all()
    return {severity: count for severity, count in rows}
