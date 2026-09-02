"""Evaluation engine: benchmark SentinelOps against synthetic incidents with
known ground truth. Scores root-cause accuracy, affected-service accuracy,
evidence quality, remediation correctness, and recovery verification.

Results are real measurements of the system against the synthetic scenarios -
not claims about production performance.
"""
from __future__ import annotations

import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.investigator import InvestigatorAgent
from app.ingestion import ingest_events, ingest_metric_points
from app.models import EvaluationCase, Evidence, Incident
from app.remediation import approve_remediation, execute_remediation, propose_remediation
from app.synthetic.generator import generate_baseline_window, generate_incident_window
from app.synthetic.scenarios import EVALUATION_SCENARIOS, Scenario
from app.verification import verify_recovery


def _seed_incident_environment(db: Session, scenario: Scenario, seed: int, incident_id_hint: str) -> Incident:
    """Generate telemetry for one scenario and create the ground-truth incident
    record with scenario_id bound (so correlation/detection has ground truth)."""
    from datetime import datetime, timedelta, timezone

    base_start = datetime.now(timezone.utc) - timedelta(minutes=65)
    base_events, base_metrics = generate_baseline_window(base_start, minutes=50, seed=seed)
    incident_start = base_start + timedelta(minutes=55)
    inc_events, inc_metrics, deployments = generate_incident_window(
        scenario, incident_start, duration_minutes=15, seed=seed
    )
    ingest_events(db, base_events, batch_id=f"eval-{scenario.scenario_id}-base")
    ingest_metric_points(db, base_metrics)
    ingest_events(db, inc_events, batch_id=f"eval-{scenario.scenario_id}-inc")
    ingest_metric_points(db, inc_metrics)
    from app.models import Deployment as DeploymentModel
    for dep in deployments:
        db.add(DeploymentModel(
            id=f"dep-{uuid.uuid4().hex[:12]}",
            timestamp=dep["timestamp"],
            service=dep["service"],
            version=dep["version"],
            commit=dep.get("commit", ""),
            actor=dep.get("actor", "ci-system"),
            notes=dep.get("notes", ""),
        ))
    db.commit()

    incident = Incident(
        id=incident_id_hint,
        title=f"[EVAL] {scenario.title}",
        status="open",
        severity=scenario.severity,
        confidence=0.0,
        category=scenario.category,
        started_at=incident_start,
        detected_at=incident_start + timedelta(minutes=15),
        affected_services=list(scenario.expected_affected_services),
        signals=[
            {"kind": "metric", "service": p.service, "metric": p.metric}
            for p in scenario.metrics[:6]
        ],
        scenario_id=scenario.scenario_id,
    )
    db.add(incident)
    db.commit()
    return incident


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _concept_match(predicted: str, concepts: list[str]) -> bool:
    """A root cause 'matches' if every core concept appears in the prediction."""
    if not predicted:
        return False
    for concept in concepts:
        parts = concept.split()
        if not any(part in predicted for part in parts):
            return False
    return True


def score_case(scenario_db: Session, main_db: Session, scenario: Scenario, incident: Incident,
               run) -> EvaluationCase:
    """Compare investigation output against the scenario's known root cause.

    Investigation artifacts (hypotheses, evidence, remediations, verifications)
    live in the scenario's isolated session; the scored EvaluationCase persists
    in the main application database."""
    from app.models import Hypothesis, Verification

    hyps = scenario_db.execute(
        select(Hypothesis).where(Hypothesis.incident_id == incident.id).order_by(Hypothesis.rank)
    ).scalars().all()
    evidence_rows = scenario_db.execute(select(Evidence).where(Evidence.incident_id == incident.id)).scalars().all()

    top = hyps[0] if hyps else None
    predicted = _normalize(top.statement) if top else ""
    known = _normalize(scenario.known_root_cause)

    rc_correct = _concept_match(predicted, [c.lower() for c in scenario.root_cause_concepts])

    predicted_services = set(incident.affected_services or [])
    expected_services = set(scenario.expected_affected_services)
    svc_overlap = predicted_services & expected_services
    svc_correct = len(svc_overlap) >= max(1, len(expected_services) - 1)

    remediation_correct: bool | None = None
    from app.models import Remediation
    rems = scenario_db.execute(select(Remediation).where(Remediation.incident_id == incident.id)).scalars().all()
    if rems:
        remediation_correct = any(r.action in scenario.acceptable_remediations for r in rems)

    verifs = scenario_db.execute(select(Verification).where(Verification.incident_id == incident.id)).scalars().all()
    recovery_verified = bool(verifs and verifs[-1].outcome in ("recovered", "partial"))

    tool_calls = run.tool_calls if hasattr(run, "tool_calls") else []
    n_tools = len(tool_calls) if tool_calls else 0
    failed_tools = sum(1 for t in tool_calls if t.get("status") == "error") if tool_calls else 0

    score = 0.0
    if rc_correct:
        score += 0.4
    if svc_correct:
        score += 0.2
    if remediation_correct:
        score += 0.2
    if recovery_verified:
        score += 0.1
    if evidence_rows:
        score += 0.1 * min(1.0, len(evidence_rows) / 5)

    case = EvaluationCase(
        id=f"evalcase-{uuid.uuid4().hex[:12]}",
        scenario_id=scenario.scenario_id,
        incident_id=incident.id,
        known_root_cause=scenario.known_root_cause,
        expected_services=scenario.expected_affected_services,
        predicted_root_cause=top.statement if top else None,
        root_cause_correct=rc_correct,
        affected_services_correct=svc_correct,
        evidence_count=len(evidence_rows),
        remediation_correct=remediation_correct,
        recovery_verified=recovery_verified,
        tool_calls=n_tools,
        failed_tool_calls=failed_tools,
        investigation_duration_ms=round(getattr(run, "_duration_ms", 0.0), 1),
        score=round(score, 2),
        details={"predicted": predicted, "known": known},
    )
    main_db.add(case)
    main_db.commit()
    return case


def _isolated_session():
    """A fresh in-memory DB session per benchmark scenario.

    Scenarios must not share telemetry: one scenario's stale metric values
    would pollute another's anomaly windows (a real measurement-integrity
    issue, not just noise)."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from app.models import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker_stub(engine)


def sessionmaker_stub(engine):
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()


def app_db_session():
    """A session bound to the main application database."""
    from app.db import SessionLocal

    return SessionLocal()


def run_evaluation(db: Session, seed_offset: int = 0) -> dict:
    """Run all benchmark scenarios end-to-end (detect → investigate → remediate → verify).

    Each scenario runs against an isolated in-memory telemetry store; only the
    scored EvaluationCase rows persist in the main database."""
    results: list[dict] = []
    main_db = app_db_session()  # one session for the whole run (cases stay attached)
    try:
        for i, scenario in enumerate(EVALUATION_SCENARIOS):
            incident_id = f"INC-EVAL{i + 1:02d}"
            scenario_db = _isolated_session()
            # topology seed for the isolated store
            from app.topology_engine import seed_default_topology

            seed_default_topology(scenario_db)
            incident = _seed_incident_environment(scenario_db, scenario, seed=1000 + i + seed_offset,
                                                  incident_id_hint=incident_id)

            t0 = time.monotonic()
            agent = InvestigatorAgent(scenario_db)
            result = agent.investigate(incident)
            duration_ms = (time.monotonic() - t0) * 1000
            result._duration_ms = duration_ms

            # remediation flow: propose (from investigation), approve, execute, verify
            from app.models import Remediation
            rem = scenario_db.execute(
                select(Remediation).where(Remediation.incident_id == incident.id,
                                          Remediation.status == "proposed")
            ).scalars().first()
            if rem is None and result.recommended_action:
                rem = propose_remediation(
                    scenario_db, incident,
                    action=result.recommended_action["action"],
                    target_service=result.recommended_action.get("target_service", ""),
                    reason=result.recommended_action.get("reason", ""),
                )
            if rem is not None:
                approve_remediation(scenario_db, rem.id, approver="eval-harness")
                execute_remediation(scenario_db, rem.id)
                verify_recovery(scenario_db, incident.id, rem.id)

            case = score_case(scenario_db, main_db, scenario, incident, result)
            # read attributes eagerly while attached; keep plain dicts
            results.append({
                "scenario_id": case.scenario_id,
                "incident_id": case.incident_id,
                "known_root_cause": case.known_root_cause,
                "predicted_root_cause": case.predicted_root_cause,
                "root_cause_correct": case.root_cause_correct,
                "affected_services_correct": case.affected_services_correct,
                "remediation_correct": case.remediation_correct,
                "recovery_verified": case.recovery_verified,
                "evidence_count": case.evidence_count,
                "tool_calls": case.tool_calls,
                "failed_tool_calls": case.failed_tool_calls,
                "investigation_duration_ms": case.investigation_duration_ms,
                "score": case.score,
            })
            scenario_db.close()
    finally:
        main_db.close()

    total = len(results)
    rc_acc = sum(1 for r in results if r["root_cause_correct"]) / total if total else 0
    svc_acc = sum(1 for r in results if r["affected_services_correct"]) / total if total else 0
    rem_acc = sum(1 for r in results if r["remediation_correct"]) / total if total else 0
    rec_acc = sum(1 for r in results if r["recovery_verified"]) / total if total else 0
    avg_score = sum(r["score"] or 0 for r in results) / total if total else 0
    return {
        "scenarios": [dict(r) for r in results],
        "aggregate": {
            "root_cause_accuracy": round(rc_acc, 2),
            "affected_service_accuracy": round(svc_acc, 2),
            "remediation_accuracy": round(rem_acc, 2),
            "recovery_verification_rate": round(rec_acc, 2),
            "average_score": round(avg_score, 2),
            "n_scenarios": total,
        },
    }
