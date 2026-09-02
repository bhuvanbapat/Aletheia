"""Deterministic synthetic telemetry generator.

Produces:
  1. A healthy baseline window (steady metrics + routine INFO logs).
  2. An incident window driven by a Scenario (causal metric ramps + logs).

All values are seeded and reproducible (seed configurable). Every event is
labeled raw_source="synthetic".
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import UTC, datetime, timedelta

from app.synthetic.scenarios import Scenario
from app.synthetic.topology import SYNTHETIC_SERVICES

METRIC_BASELINES: dict[str, dict[str, float]] = {
    "api-gateway": {"request_rate": 850.0, "error_rate": 0.2, "p95_latency_ms": 150.0, "cpu_percent": 35.0,
                    "memory_mb": 610.0},
    "auth-service": {"request_rate": 840.0, "error_rate": 0.3, "p95_latency_ms": 60.0, "cpu_percent": 25.0,
                     "memory_mb": 380.0, "auth_failure_rate": 0.5},
    "orders-service": {"request_rate": 310.0, "error_rate": 0.3, "p95_latency_ms": 220.0, "cpu_percent": 40.0,
                       "memory_mb": 420.0},
    "payments-service": {"request_rate": 300.0, "error_rate": 0.4, "p95_latency_ms": 180.0, "cpu_percent": 38.0,
                         "memory_mb": 540.0},
    "inventory-service": {"request_rate": 290.0, "error_rate": 0.2, "p95_latency_ms": 45.0, "cpu_percent": 22.0,
                          "memory_mb": 350.0, "cache_hit_rate": 92.0},
    "notification-service": {"request_rate": 300.0, "error_rate": 0.1, "p95_latency_ms": 300.0, "cpu_percent": 18.0,
                             "memory_mb": 300.0, "queue_depth": 4.0},
    "orders-db": {"db_latency_ms": 45.0, "db_connections": 40.0, "cpu_percent": 45.0, "db_slow_queries": 2.0},
    "inventory-db": {"db_latency_ms": 12.0, "cpu_percent": 30.0, "db_connections": 20.0},
    "auth-db": {"db_latency_ms": 8.0, "cpu_percent": 20.0, "db_connections": 12.0},
    "external-email-provider": {"send_latency_ms": 250.0, "send_error_rate": 0.5},
}

ROUTINE_LOGS: list[tuple[str, str, str]] = [
    ("INFO", "request_completed", "Request completed successfully"),
    ("INFO", "health_check", "Health check passed"),
    ("DEBUG", "cache_hit", "Cache hit for key"),
    ("INFO", "batch_processed", "Background batch processed"),
    ("INFO", "connection_pool", "Pool status nominal"),
]


def _dedup_hash(timestamp: datetime, service: str, event_type: str, message: str, seq: int) -> str:
    payload = f"{timestamp.isoformat()}|{service}|{event_type}|{message}|{seq}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def generate_baseline_window(
    start: datetime,
    minutes: int,
    seed: int,
    sample_interval_s: int = 60,
) -> tuple[list[dict], list[dict]]:
    """Healthy pre-incident telemetry. Returns (events, metric_points)."""
    rng = random.Random(seed)
    events: list[dict] = []
    metrics: list[dict] = []
    base = METRIC_BASELINES
    for svc_def in SYNTHETIC_SERVICES:
        svc = svc_def["name"]
        for mname, baseline in base.get(svc, {}).items():
            for minute in range(minutes):
                ts = start + timedelta(minutes=minute)
                for offset in range(0, 60, sample_interval_s):
                    ts_sample = ts + timedelta(seconds=offset)
                    noise_pct = 0.04
                    value = baseline * (1 + rng.uniform(-noise_pct, noise_pct))
                    if "rate" in mname or mname in ("db_slow_queries", "queue_depth", "db_connections"):
                        value = max(0.0, value)
                    metrics.append({
                        "timestamp": ts_sample,
                        "service": svc,
                        "metric_name": mname,
                        "value": round(value, 3),
                        "environment": "production",
                    })
    # routine logs - a few per service per few minutes
    for minute in range(0, minutes, 2):
        ts = start + timedelta(minutes=minute)
        for svc_def in SYNTHETIC_SERVICES:
            svc = svc_def["name"]
            for _ in range(rng.randint(1, 2)):
                severity, etype, msg = ROUTINE_LOGS[rng.randrange(len(ROUTINE_LOGS))]
                ts_event = ts + timedelta(seconds=rng.randint(0, 119))
                events.append({
                    "timestamp": ts_event,
                    "service": svc,
                    "environment": "production",
                    "severity": severity,
                    "event_type": etype,
                    "message": msg,
                    "metadata": {},
                    "trace_id": f"tr-base-{rng.randint(10000, 99999)}",
                    "dedup_hash": _dedup_hash(ts_event, svc, etype, msg, len(events)),
                    "raw_source": "synthetic",
                })
    return events, metrics


def _incident_curve(frac: float, baseline: float, peak: float, plateau: bool = True) -> float:
    """Smooth S-curve from baseline to peak over frac∈[0,1]."""
    if frac <= 0:
        return baseline
    if frac >= 1:
        return peak if plateau else baseline
    s = 1 / (1 + math.exp(-(frac - 0.5) * 10))
    return baseline + (peak - baseline) * s


def generate_incident_window(
    scenario: Scenario,
    incident_start: datetime,
    duration_minutes: int,
    seed: int,
    sample_interval_s: int = 60,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Incident telemetry. Returns (events, metric_points, deployments).

    Metric semantics: each MetricProfile ramps baseline→peak over ramp_minutes,
    then plateaus at peak until the end of the window (incident unmitigated).
    """
    rng = random.Random(seed + 7)
    events: list[dict] = []
    metrics: list[dict] = []
    deployments: list[dict] = []

    # scenario metrics
    for minute in range(duration_minutes + 1):
        ts_minute = incident_start + timedelta(minutes=minute)
        for profile in scenario.metrics:
            # this metric belongs to a service with a baseline (use scenario baseline)
            base = profile.baseline
            peak = profile.peak
            ramp = profile.ramp_minutes
            if ramp <= 0:
                ramp = 1
            frac = min(1.0, minute / ramp)
            value = _incident_curve(frac, base, peak)
            for offset in range(0, 60, sample_interval_s):
                ts = ts_minute + timedelta(seconds=offset)
                noise = value * rng.uniform(-0.03, 0.03)
                metrics.append({
                    "timestamp": ts,
                    "service": profile.service,
                    "metric_name": profile.metric,
                    "value": round(max(0.0, value + noise), 3),
                    "environment": "production",
                })

    # scenario logs (offsets relative to incident start)
    for i, log in enumerate(scenario.logs):
        ts = incident_start + timedelta(minutes=log.offset_minutes, seconds=rng.randint(0, 50))
        metadata = dict(log.metadata)
        events.append({
            "timestamp": ts,
            "service": log.service,
            "environment": "production",
            "severity": log.severity,
            "event_type": log.event_type,
            "message": log.message,
            "metadata": metadata,
            "trace_id": metadata.get("trace_id") or f"tr-inc-{rng.randint(10000, 99999)}",
            "dedup_hash": _dedup_hash(ts, log.service, log.event_type, log.message, i),
            "raw_source": "synthetic",
        })

    # healthy services continue routine background telemetry (light)
    healthy = [s for s in SYNTHETIC_SERVICES if s["name"] not in {p.service for p in scenario.metrics}]
    for minute in range(0, duration_minutes, 3):
        ts = incident_start + timedelta(minutes=minute)
        for svc_def in healthy:
            svc = svc_def["name"]
            for mname, baseline in base_metrics(svc).items():
                value = baseline * (1 + rng.uniform(-0.04, 0.04))
                metrics.append({
                    "timestamp": ts,
                    "service": svc,
                    "metric_name": mname,
                    "value": round(max(0.0, value), 3),
                    "environment": "production",
                })

    # deployment event if scenario is deployment-driven
    if scenario.deployment:
        dep = scenario.deployment
        dep_ts = incident_start + timedelta(minutes=scenario.logs[0].offset_minutes if scenario.logs else 0)
        deployments.append({
            "timestamp": dep_ts,
            "service": dep["service"],
            "version": dep["version"],
            "commit": dep["commit"],
            "actor": dep["actor"],
            "notes": dep["notes"],
            "environment": "production",
        })

    return events, metrics, deployments


def base_metrics(service: str) -> dict[str, float]:
    return METRIC_BASELINES.get(service, {})


def generate_post_remediation_window(
    scenario: Scenario,
    remediation_time: datetime,
    minutes: int,
    seed: int,
    sample_interval_s: int = 60,
) -> list[dict]:
    """Post-remediation recovery telemetry: scenario metrics decay back toward baseline."""
    rng = random.Random(seed + 13)
    metrics: list[dict] = []
    for profile in scenario.metrics:
        max(1, profile.ramp_minutes)
        recovery = max(1, profile.recovery_minutes)
        # state at remediation time = peak (incident unmitigated until then)
        for minute in range(minutes + 1):
            frac = min(1.0, minute / recovery)
            value = profile.peak + (profile.baseline - profile.peak) * frac
            ts_minute = remediation_time + timedelta(minutes=minute)
            for offset in range(0, 60, sample_interval_s):
                ts = ts_minute + timedelta(seconds=offset)
                noise = value * rng.uniform(-0.03, 0.03)
                metrics.append({
                    "timestamp": ts,
                    "service": profile.service,
                    "metric_name": profile.metric,
                    "value": round(max(0.0, value + noise), 3),
                    "environment": "production",
                })
    return metrics


def utc_now() -> datetime:
    return datetime.now(UTC)
