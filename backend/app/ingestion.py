"""Telemetry ingestion: parsing, normalization, deduplication, resilience.

Handles malformed input gracefully: malformed entries are skipped and counted,
never crash the batch. Duplicate events are detected via dedup_hash.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IngestionStats, TelemetryEvent

VALID_SEVERITIES = {"DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"}

_seen_hashes: set[str] | None = None


def _reset_dedup_cache() -> None:
    global _seen_hashes
    _seen_hashes = None


def _load_hash_cache(db: Session) -> set[str]:
    global _seen_hashes
    if _seen_hashes is None:
        _seen_hashes = {h for (h,) in db.execute(select(TelemetryEvent.dedup_hash)).all()}
    return _seen_hashes


def _compute_dedup_hash(event: dict[str, Any]) -> str:
    payload = "|".join([
        str(event.get("timestamp", "")),
        str(event.get("service", "")),
        str(event.get("event_type", "")),
        str(event.get("message", "")),
        json.dumps(event.get("metadata", {}), sort_keys=True),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)  # type: ignore[arg-type]
        except Exception:
            return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def normalize_event(raw: dict[str, Any], seq: int = 0) -> dict[str, Any] | None:
    """Normalize one raw event. Returns internal representation or None if malformed."""
    if not isinstance(raw, dict):
        return None
    ts = _parse_timestamp(raw.get("timestamp"))
    service = raw.get("service")
    if ts is None or not service or not isinstance(service, str):
        return None
    severity = str(raw.get("severity", "INFO")).upper()
    if severity not in VALID_SEVERITIES:
        severity = "INFO"
    event_type = str(raw.get("event_type", "generic"))[:64]
    message = str(raw.get("message", ""))[:2000]
    metadata = raw.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {"_original_metadata": str(metadata)[:500]}
    normalized = {
        "timestamp": ts,
        "service": service[:64],
        "environment": str(raw.get("environment", "production"))[:64],
        "severity": severity,
        "event_type": event_type,
        "message": message,
        "metadata": metadata,
        "trace_id": (str(raw.get("trace_id"))[:64] if raw.get("trace_id") else None),
        "raw_source": str(raw.get("raw_source", "external"))[:16],
    }
    normalized["dedup_hash"] = (
        str(raw["dedup_hash"])[:40] if raw.get("dedup_hash") else _compute_dedup_hash(normalized)
    )
    return normalized


def ingest_events(db: Session, raw_events: list[dict[str, Any]], batch_id: str = "") -> dict[str, Any]:
    """Ingest a batch of raw events. Returns ingestion stats. Never raises on bad input."""
    received = len(raw_events)
    accepted = 0
    duplicates = 0
    malformed = 0
    parse_errors: list[str] = []

    seen = _load_hash_cache(db)
    new_events: list[TelemetryEvent] = []

    for i, raw in enumerate(raw_events):
        try:
            normalized = normalize_event(raw, seq=i)
        except Exception as exc:  # defensive: normalization must never crash
            malformed += 1
            if len(parse_errors) < 20:
                parse_errors.append(f"item {i}: {type(exc).__name__}: {exc}")
            continue
        if normalized is None:
            malformed += 1
            if len(parse_errors) < 20:
                parse_errors.append(f"item {i}: missing/invalid timestamp or service")
            continue
        if normalized["dedup_hash"] in seen:
            duplicates += 1
            continue
        seen.add(normalized["dedup_hash"])
        new_events.append(
            TelemetryEvent(
                id=f"tev-{hashlib.sha256((normalized['dedup_hash'] + str(i)).encode()).hexdigest()[:16]}",
                timestamp=normalized["timestamp"],
                service=normalized["service"],
                environment=normalized["environment"],
                severity=normalized["severity"],
                event_type=normalized["event_type"],
                message=normalized["message"],
                metadata_json=normalized["metadata"],
                trace_id=normalized["trace_id"],
                dedup_hash=normalized["dedup_hash"],
                raw_source=normalized["raw_source"],
            )
        )
        accepted += 1

    if new_events:
        db.add_all(new_events)
    db.add(
        IngestionStats(
            batch_id=batch_id,
            received=received,
            accepted=accepted,
            duplicates=duplicates,
            malformed=malformed,
            parse_errors=parse_errors,
        )
    )
    db.commit()
    return {
        "received": received,
        "accepted": accepted,
        "duplicates": duplicates,
        "malformed": malformed,
        "parse_errors": parse_errors,
    }


def ingest_metric_points(db: Session, points: list[dict[str, Any]]) -> int:
    """Ingest metric samples. Returns count stored."""
    from app.models import MetricPoint

    stored = 0
    chunk: list[MetricPoint] = []
    for p in points:
        ts = _parse_timestamp(p.get("timestamp"))
        service = p.get("service")
        name = p.get("metric_name")
        value = p.get("value")
        if ts is None or not service or not name or not isinstance(value, (int, float)):
            continue
        chunk.append(
            MetricPoint(
                timestamp=ts,
                service=str(service)[:64],
                metric_name=str(name)[:64],
                value=float(value),
                environment=str(p.get("environment", "production"))[:64],
            )
        )
        stored += 1
    if chunk:
        db.add_all(chunk)
        db.commit()
    return stored
