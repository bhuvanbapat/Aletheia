"""Remediation engine: controlled actions against the synthetic environment.

SAFETY: only whitelisted actions, executed purely in-simulation. No host
commands, no subprocess, no real infrastructure. Every action records
initiator, reason, params, expected effect, and actual result.
Approval is REQUIRED by default (remediation_mode=approval_required).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Incident, Remediation, TelemetryEvent
from app.synthetic.generator import generate_post_remediation_window
from app.synthetic.scenarios import SCENARIOS

ALLOWED_ACTIONS = {
    "rollback_deployment",
    "restart_service",
    "scale_service",
    "clear_cache",
    "increase_connection_pool",
    "disable_feature_flag",
}

# Effects modeled in the synthetic environment (descriptions only; the actual
# recovery data is generated as post-remediation telemetry).
ACTION_EFFECTS = {
    "rollback_deployment": "Previous version restored; connection/code behavior returns to pre-incident state",
    "restart_service": "Service processes restart; memory cleared, connection pools re-established",
    "scale_service": "Additional instances absorb load; per-instance pressure decreases",
    "clear_cache": "Cache entries flushed; cache repopulates with consistent data",
    "increase_connection_pool": "Pool limit raised; queued requests acquire connections",
    "disable_feature_flag": "Feature path disabled; traffic bypasses the faulty code path",
}


@dataclass
class RemediationOutcome:
    remediation_id: str
    status: str
    result: str
    executed: bool


def propose_remediation(db: Session, incident: Incident, action: str, target_service: str,
                        reason: str, expected_effect: str = "", risk: str = "medium") -> Remediation:
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"action '{action}' not allowed. Allowed: {sorted(ALLOWED_ACTIONS)}")
    rem = Remediation(
        id=f"rem-{uuid.uuid4().hex[:12]}",
        incident_id=incident.id,
        action=action,
        target_service=target_service,
        params={},
        reason=reason,
        expected_effect=expected_effect or ACTION_EFFECTS.get(action, ""),
        risk=risk,
        status="proposed",
        approval_state="pending",
        initiated_by="operator",
    )
    db.add(rem)
    db.commit()
    return rem


def approve_remediation(db: Session, remediation_id: str, approver: str = "human-operator") -> Remediation | None:
    rem = db.get(Remediation, remediation_id)
    if rem is None:
        return None
    if rem.approval_state == "approved":
        return rem
    rem.approval_state = "approved"
    rem.approved_by = approver
    rem.status = "approved"
    db.commit()
    return rem


def reject_remediation(db: Session, remediation_id: str) -> Remediation | None:
    rem = db.get(Remediation, remediation_id)
    if rem is None:
        return None
    rem.approval_state = "rejected"
    rem.status = "rejected"
    db.commit()
    return rem


def execute_remediation(db: Session, remediation_id: str, simulator=None) -> RemediationOutcome:
    """Execute an APPROVED remediation against the synthetic environment.

    The simulator generates post-remediation recovery telemetry so recovery
    verification is based on actual (synthetic) measurements, not claims.
    """
    rem = db.get(Remediation, remediation_id)
    if rem is None:
        return RemediationOutcome(remediation_id=remediation_id, status="not_found",
                                  result="remediation not found", executed=False)
    settings = get_settings()
    mode = settings.remediation_mode
    if mode in ("analysis", "recommend") :
        return RemediationOutcome(remediation_id=rem.id, status="blocked",
                                  result=f"remediation mode '{mode}' forbids execution", executed=False)
    if mode == "approval_required" and rem.approval_state != "approved":
        return RemediationOutcome(remediation_id=rem.id, status="blocked",
                                  result="approval required before execution", executed=False)

    incident = db.get(Incident, rem.incident_id)
    scenario = SCENARIOS.get(incident.scenario_id) if incident and incident.scenario_id else None

    from datetime import datetime

    executed_at = datetime.now(UTC)
    # simulate action effect: recovery telemetry (against the synthetic env only)
    generated_points = 0
    if scenario is not None:
        points = generate_post_remediation_window(scenario, executed_at, minutes=12, seed=99)
        from app.ingestion import ingest_metric_points
        generated_points = ingest_metric_points(db, points)
        # recovery completion log
        db.add(TelemetryEvent(
            id=f"tev-{uuid.uuid4().hex[:16]}",
            timestamp=executed_at,
            service=rem.target_service or scenario.root_service,
            environment="production",
            severity="INFO",
            event_type="remediation_applied",
            message=f"Remediation {rem.action} applied ({rem.id})",
            metadata_json={"remediation_id": rem.id, "simulated": True},
            trace_id=None,
            dedup_hash=uuid.uuid4().hex,
            raw_source="synthetic",
        ))
        db.commit()

    rem.status = "executed"
    rem.executed_at = executed_at
    rem.result = (
        f"Simulated execution of {rem.action}"
        + (f" on {rem.target_service}" if rem.target_service else "")
        + f"; recovery telemetry generated ({generated_points} points)"
    )
    if incident is not None:
        incident.status = "mitigated"
    db.commit()
    return RemediationOutcome(remediation_id=rem.id, status="executed", result=rem.result, executed=True)


def remediation_to_dict(rem: Remediation) -> dict:
    return {
        "id": rem.id,
        "incident_id": rem.incident_id,
        "action": rem.action,
        "target_service": rem.target_service,
        "reason": rem.reason,
        "expected_effect": rem.expected_effect,
        "risk": rem.risk,
        "status": rem.status,
        "approval_state": rem.approval_state,
        "initiated_by": rem.initiated_by,
        "approved_by": rem.approved_by,
        "executed_at": rem.executed_at,
        "result": rem.result,
    }
