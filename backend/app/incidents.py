"""Incident manager: lifecycle, detection from correlation results, timeline."""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.incident_rules import RuleResult, run_correlation
from app.models import Evidence, Incident, TelemetryEvent


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def detect_incidents(db: Session, window_minutes: int = 30, scenario_id: str | None = None) -> list[Incident]:
    """Run correlation rules and create incidents for new findings.

    Deduplication: skip if an open incident already exists with the same
    category AND overlapping affected services (one incident, not alert storms).
    """
    results = run_correlation(db, window_minutes=window_minutes)
    created: list[Incident] = []
    existing = list(db.execute(select(Incident).where(Incident.status != "resolved")).scalars().all())

    for result in results:
        dup = None
        for inc in existing:
            if inc.category == result.category and set(inc.affected_services or []) & set(result.affected_services):
                dup = inc
                break
        if dup is not None:
            continue

        started = utcnow() - timedelta(minutes=window_minutes)
        incident = Incident(
            id=f"INC-{uuid.uuid4().hex[:8].upper()}",
            title=_title_for(result),
            status="open",
            severity=result.severity,
            confidence=result.confidence,
            category=result.category,
            started_at=started,
            detected_at=utcnow(),
            affected_services=result.affected_services,
            signals=[s if isinstance(s, dict) else asdict(s) for s in result.signals],
            scenario_id=scenario_id,
        )
        db.add(incident)
        db.flush()
        for hint in result.evidence_hints:
            db.add(Evidence(
                id=f"ev-{uuid.uuid4().hex[:12]}",
                incident_id=incident.id,
                kind="analysis",
                description=hint,
                source_ref="correlation-engine",
            ))
        created.append(incident)
        existing.append(incident)
    if created:
        db.commit()
    return created


def _title_for(result: RuleResult) -> str:
    labels = {
        "database_exhaustion": "Database capacity exhaustion",
        "deployment_regression": "Deployment regression",
        "resource_saturation": "Resource saturation",
        "memory_leak": "Memory leak / resource saturation",
        "cache_failure": "Cache failure",
        "dependency_timeout": "Dependency timeout",
    }
    label = labels.get(result.category, result.category.replace("_", " ").title())
    return f"{label} originating at {result.primary_service}"


def incident_to_dict(inc: Incident, include_related: bool = False) -> dict:
    out = {
        "id": inc.id,
        "title": inc.title,
        "status": inc.status,
        "severity": inc.severity,
        "confidence": inc.confidence,
        "category": inc.category,
        "started_at": inc.started_at,
        "detected_at": inc.detected_at,
        "resolved_at": inc.resolved_at,
        "affected_services": inc.affected_services or [],
        "signals": inc.signals or [],
        "root_cause": inc.root_cause,
        "root_cause_confidence": inc.root_cause_confidence,
        "scenario_id": inc.scenario_id,
    }
    return out


def build_timeline(db: Session, incident: Incident) -> list[dict]:
    """Incident timeline from signals, logs, deployments, and lifecycle events."""
    entries: list[dict] = []
    for signal in incident.signals or []:
        if isinstance(signal, dict):
            ts = signal.get("deployed_at") or signal.get("explanation", "")
            deployed = signal.get("deployed_at")
            if deployed:
                entries.append({
                    "timestamp": deployed,
                    "kind": "deployment",
                    "label": f"Deployment {signal.get('service')} {signal.get('version', '')}",
                })
    # ERROR/CRITICAL logs within the incident window for affected services
    cutoff = incident.started_at - timedelta(minutes=5)
    services = set(incident.affected_services or [])
    logs = db.execute(
        select(TelemetryEvent).where(
            TelemetryEvent.severity.in_(["ERROR", "CRITICAL"]),
            TelemetryEvent.timestamp >= cutoff,
        ).order_by(TelemetryEvent.timestamp)
    ).scalars().all()
    for log in logs:
        if log.service in services:
            entries.append({
                "timestamp": log.timestamp.isoformat(),
                "kind": "log",
                "label": f"[{log.severity}] {log.service}: {log.message[:90]}",
            })
    entries.append({"timestamp": incident.detected_at.isoformat(), "kind": "incident", "label": f"Incident {incident.id} detected ({incident.severity})"})
    entries.sort(key=lambda e: e["timestamp"])
    return entries
