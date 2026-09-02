"""Recovery verification: measure, never claim.

A remediation is only 'recovered' if post-remediation telemetry demonstrates
return toward baseline. Outcomes: recovered | partial | not_recovered | unknown.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.metrics_engine import compute_baseline, query_series
from app.models import Incident, Remediation, Verification

RECOVERY_THRESHOLD_PCT = 0.30  # metric must close >=30% of the (peak-baseline) gap
PARTIAL_THRESHOLD_PCT = 0.60


def verify_recovery(db: Session, incident_id: str, remediation_id: str | None = None) -> Verification | None:
    incident = db.get(Incident, incident_id)
    if incident is None:
        return None
    rem = db.get(Remediation, remediation_id) if remediation_id else None

    reference_time = rem.executed_at if (rem and rem.executed_at) else incident.detected_at
    checked: list[dict] = []
    evidence: list[str] = []

    # metrics to check: those named in incident signals
    targets: list[tuple[str, str]] = []
    for sig in incident.signals or []:
        if isinstance(sig, dict) and sig.get("kind") == "metric" and sig.get("service") and sig.get("metric"):
            targets.append((sig["service"], sig["metric"]))
    if not targets:
        # fall back: error_rate/p95 of affected services
        for svc in (incident.affected_services or [])[:4]:
            targets.append((svc, "error_rate"))
            targets.append((svc, "p95_latency_ms"))

    recovered_count = 0
    unknown_count = 0
    for service, metric in targets[:10]:
        series = query_series(db, service, metric)
        if not series:
            unknown_count += 1
            continue
        pre = [p for p in series if p["timestamp"] <= reference_time]
        post = [p for p in series if p["timestamp"] > reference_time]
        if len(post) < 3:
            # not enough post-remediation data yet
            checked.append({"service": service, "metric": metric, "outcome": "unknown",
                            "reason": "insufficient post-remediation samples"})
            unknown_count += 1
            continue
        pre_baseline = compute_baseline(pre[-30:]) if pre else None
        if pre_baseline is None:
            checked.append({"service": service, "metric": metric, "outcome": "unknown",
                            "reason": "no pre-remediation baseline"})
            unknown_count += 1
            continue
        pre_values = [p["value"] for p in pre[-30:]]
        peak = max(pre_values) if pre_values else pre_baseline["mean"]
        post_mean = sum(p["value"] for p in post) / len(post)
        gap = peak - pre_baseline["mean"]
        if abs(gap) < 1e-9:
            checked.append({"service": service, "metric": metric, "outcome": "recovered",
                            "reason": "no material deviation existed"})
            recovered_count += 1
            continue
        closure = (peak - post_mean) / gap  # fraction of the gap that closed
        if closure >= (1 - PARTIAL_THRESHOLD_PCT):
            outcome = "recovered"
        elif closure >= (1 - RECOVERY_THRESHOLD_PCT * 2):
            outcome = "partial"
        else:
            outcome = "not_recovered"
        if outcome == "recovered":
            recovered_count += 1
        checked.append({
            "service": service, "metric": metric, "outcome": outcome,
            "pre_peak": round(peak, 3), "post_mean": round(post_mean, 3),
            "baseline": round(pre_baseline["mean"], 3),
            "gap_closed_pct": round(closure * 100, 1),
        })
        evidence.append(
            f"{service}/{metric}: peak {peak:.1f} -> post-remediation avg {post_mean:.1f} "
            f"(baseline {pre_baseline['mean']:.1f}; {closure * 100:.0f}% of gap closed)"
        )

    total_measured = len(checked) - unknown_count
    if total_measured == 0:
        outcome = "unknown"
    elif recovered_count == total_measured:
        outcome = "recovered"
    elif recovered_count > 0:
        outcome = "partial"
    else:
        outcome = "not_recovered"

    if outcome == "recovered":
        incident.resolved_at = datetime.now(timezone.utc)
        incident.status = "resolved"
        evidence.append(f"All {total_measured} measured signals returned to baseline range")
    elif outcome == "partial":
        incident.status = "mitigated"
        evidence.append(f"{recovered_count}/{total_measured} measured signals recovered")
    elif outcome == "not_recovered":
        evidence.append(f"0/{total_measured} measured signals recovered")

    verification = Verification(
        id=f"ver-{uuid.uuid4().hex[:12]}",
        incident_id=incident.id,
        remediation_id=remediation_id,
        outcome=outcome,
        checked_metrics=checked,
        evidence=evidence,
    )
    db.add(verification)
    db.commit()
    return verification


def verification_to_dict(v: Verification) -> dict:
    return {
        "id": v.id,
        "incident_id": v.incident_id,
        "remediation_id": v.remediation_id,
        "outcome": v.outcome,
        "checked_metrics": v.checked_metrics or [],
        "evidence": v.evidence or [],
        "checked_at": v.checked_at,
        "notes": v.notes,
    }
