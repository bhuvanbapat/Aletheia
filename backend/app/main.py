"""SentinelOps FastAPI application."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.investigator import investigate_incident
from app.ai.tools import ToolRegistry
from app.bootstrap import bootstrap_demo
from app.config import get_settings
from app.db import get_db, init_db
from app.evaluation import run_evaluation
from app.incidents import build_timeline, detect_incidents, incident_to_dict
from app.log_engine import count_logs, event_to_dict, log_stats, query_logs
from app.metrics_engine import detect_anomalies, query_series, summarize_service_metrics
from app.models import (AgentRun, Deployment, Evidence, Hypothesis, Incident, Postmortem,
                        Remediation, Service, TelemetryEvent, ToolCall, Verification)
from app.postmortem import generate_postmortem, postmortem_to_dict
from app.remediation import (approve_remediation, execute_remediation, propose_remediation,
                             remediation_to_dict)
from app.schemas import ApprovalRequest, ExecuteRequest, IngestResponse, SettingsOut, TelemetryEventIn
from app.security import contains_injection_markers, quarantine_explanation, redact_mapping
from app.topology_engine import load_topology, topology_dict
from app.verification import verification_to_dict, verify_recovery

settings = get_settings()


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        bootstrap_demo(db, run_flagship_incident=True)
    finally:
        db.close()
    yield


app = FastAPI(
    title="SentinelOps API",
    description="AI SRE & Incident Intelligence Platform - synthetic environment demo",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- health ----------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment,
            "synthetic": True, "time": datetime.now(timezone.utc).isoformat()}


# ---------------- services & topology ----------------

@app.get("/api/services")
def list_services(db: Session = Depends(get_db)) -> list[dict]:
    services = db.execute(select(Service)).scalars().all()
    graph = load_topology(db)
    out = []
    for svc in services:
        series = query_series(db, svc.name, "error_rate")
        latest_err = series[-1]["value"] if series else None
        out.append({
            "name": svc.name,
            "kind": svc.kind,
            "description": svc.description,
            "dependencies": graph.downstream(svc.name),
            "dependents": graph.upstream(svc.name),
            "error_rate": latest_err,
        })
    return out


@app.get("/api/services/{name}/metrics")
def service_metrics(name: str, window_minutes: int = 15, db: Session = Depends(get_db)) -> dict:
    return summarize_service_metrics(db, name, window_minutes)


@app.get("/api/topology")
def get_topology(db: Session = Depends(get_db)) -> dict:
    return topology_dict(load_topology(db))


@app.get("/api/topology/impact/{service}")
def impact(service: str, db: Session = Depends(get_db)) -> dict:
    graph = load_topology(db)
    if service not in graph.nodes:
        raise HTTPException(404, f"unknown service {service}")
    return {"service": service,
            "affected_if_degraded": graph.impact_radius(service),
            "propagation": graph.propagation_path(service)}


# ---------------- telemetry ingestion ----------------

def _event_in_to_raw(e: TelemetryEventIn) -> dict:
    return e.model_dump()


@app.post("/api/telemetry", response_model=IngestResponse)
def ingest_telemetry(events: list[TelemetryEventIn], db: Session = Depends(get_db)) -> IngestResponse:
    """Ingest a batch of telemetry events (malformed entries skipped+counted)."""
    from app.ingestion import ingest_events

    raws = []
    for e in events:
        raw = _event_in_to_raw(e)
        # security: redact secrets, flag injection markers
        clean_meta, _ = redact_mapping(raw.get("metadata", {}))
        raw["metadata"] = clean_meta
        flagged = contains_injection_markers(raw.get("message", "")) or contains_injection_markers(str(raw.get("metadata")))
        if flagged:
            raw["metadata"] = {**raw["metadata"], "_quarantine": True,
                               "_quarantine_reason": quarantine_explanation(True)}
        raws.append(raw)
    stats = ingest_events(db, raws, batch_id=f"api-{datetime.now(timezone.utc).strftime('%H%M%S')}")
    return IngestResponse(**stats)


@app.get("/api/telemetry/stats")
def telemetry_stats(db: Session = Depends(get_db)) -> dict:
    from app.models import IngestionStats

    total = db.execute(select(func.sum(IngestionStats.accepted))).scalar() or 0
    malformed = db.execute(select(func.sum(IngestionStats.malformed))).scalar() or 0
    dupes = db.execute(select(func.sum(IngestionStats.duplicates))).scalar() or 0
    return {"accepted_total": int(total), "malformed_total": int(malformed), "duplicates_total": int(dupes)}


# ---------------- logs ----------------

@app.get("/api/logs")
def logs(
    service: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
    search: str | None = None,
    trace_id: str | None = None,
    minutes: int = 60,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    latest = db.execute(select(func.max(TelemetryEvent.timestamp))).scalar()
    end = latest
    start = (latest or datetime.now(timezone.utc)) - timedelta(minutes=minutes)
    rows = query_logs(db, service=service, severity=severity, event_type=event_type,
                      start=start, end=end, search=search, trace_id=trace_id,
                      limit=limit, offset=offset)
    total = count_logs(db, service=service, severity=severity, event_type=event_type,
                       start=start, end=end, search=search)
    return {"total": total, "items": [event_to_dict(r) for r in rows]}


@app.get("/api/logs/stats")
def logs_stats(db: Session = Depends(get_db)) -> dict:
    return log_stats(db, window_minutes=60)


# ---------------- metrics ----------------

@app.get("/api/metrics")
def metrics(service: str, metric: str, minutes: int = 60, db: Session = Depends(get_db)) -> dict:
    latest = db.execute(select(func.max(TelemetryEvent.timestamp))).scalar()
    start = (latest or datetime.now(timezone.utc)) - timedelta(minutes=minutes)
    series = query_series(db, service, metric, start=start)
    anomalies = detect_anomalies(query_series(db, service, metric), service, metric)
    return {
        "service": service,
        "metric": metric,
        "series": [{"timestamp": p["timestamp"].isoformat(), "value": p["value"]} for p in series],
        "anomalies": [a.to_dict() for a in anomalies],
    }


# ---------------- deployments ----------------

@app.get("/api/deployments")
def deployments(hours: int = 24, db: Session = Depends(get_db)) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = db.execute(
        select(Deployment).where(Deployment.timestamp >= cutoff).order_by(Deployment.timestamp.desc())
    ).scalars().all()
    return [
        {"id": d.id, "timestamp": d.timestamp, "service": d.service, "version": d.version,
         "commit": d.commit, "actor": d.actor, "notes": d.notes}
        for d in rows
    ]


# ---------------- incidents ----------------

@app.get("/api/incidents")
def incidents(status: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(Incident).order_by(Incident.detected_at.desc())
    if status:
        stmt = stmt.where(Incident.status == status)
    rows = db.execute(stmt).scalars().all()
    return [incident_to_dict(r) for r in rows]


@app.post("/api/incidents/detect")
def detect(db: Session = Depends(get_db)) -> dict:
    created = detect_incidents(db, window_minutes=30)
    return {"created": [incident_to_dict(i) for i in created]}


@app.get("/api/incidents/{incident_id}")
def incident_detail(incident_id: str, db: Session = Depends(get_db)) -> dict:
    inc = db.get(Incident, incident_id)
    if inc is None:
        raise HTTPException(404, "incident not found")
    return incident_to_dict(inc)


@app.get("/api/incidents/{incident_id}/timeline")
def incident_timeline(incident_id: str, db: Session = Depends(get_db)) -> list[dict]:
    inc = db.get(Incident, incident_id)
    if inc is None:
        raise HTTPException(404, "incident not found")
    return build_timeline(db, inc)


@app.get("/api/incidents/{incident_id}/evidence")
def incident_evidence(incident_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(Evidence).where(Evidence.incident_id == incident_id)).scalars().all()
    return [
        {"id": e.id, "kind": e.kind, "description": e.description, "source_ref": e.source_ref,
         "observed_at": e.observed_at}
        for e in rows
    ]


@app.get("/api/incidents/{incident_id}/hypotheses")
def incident_hypotheses(incident_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(Hypothesis).where(Hypothesis.incident_id == incident_id).order_by(Hypothesis.rank)
    ).scalars().all()
    return [
        {"id": h.id, "statement": h.statement, "confidence": h.confidence,
         "evidence_for": h.evidence_for, "evidence_against": h.evidence_against,
         "rank": h.rank, "verdict": h.verdict}
        for h in rows
    ]


@app.post("/api/incidents/{incident_id}/investigate")
def investigate(incident_id: str, db: Session = Depends(get_db)) -> dict:
    result = investigate_incident(db, incident_id)
    if result is None:
        raise HTTPException(404, "incident not found")
    return {
        "run_id": result.run_id, "incident_id": result.incident_id, "status": result.status,
        "hypotheses": result.hypotheses, "root_cause": result.root_cause,
        "root_cause_confidence": result.root_cause_confidence,
        "recommended_action": result.recommended_action, "summary": result.summary,
        "stop_reason": result.stop_reason, "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens, "llm_request_count": result.llm_request_count,
        "tool_calls": result.tool_calls,
        "demo_mode": not get_settings().llm_enabled,
    }


# ---------------- remediation & verification ----------------

@app.get("/api/incidents/{incident_id}/remediations")
def incident_remediations(incident_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(Remediation).where(Remediation.incident_id == incident_id)).scalars().all()
    return [remediation_to_dict(r) for r in rows]


@app.post("/api/incidents/{incident_id}/remediate")
def remediate(incident_id: str, body: dict, db: Session = Depends(get_db)) -> dict:
    inc = db.get(Incident, incident_id)
    if inc is None:
        raise HTTPException(404, "incident not found")
    action = body.get("action", "")
    try:
        rem = propose_remediation(db, inc, action=action,
                                  target_service=body.get("target_service", ""),
                                  reason=body.get("reason", ""),
                                  expected_effect=body.get("expected_effect", ""),
                                  risk=body.get("risk", "medium"))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return remediation_to_dict(rem)


@app.post("/api/remediations/{remediation_id}/approve")
def approve(remediation_id: str, body: ApprovalRequest, db: Session = Depends(get_db)) -> dict:
    if body.approved:
        rem = approve_remediation(db, remediation_id, approver=body.approver)
    else:
        from app.remediation import reject_remediation

        rem = reject_remediation(db, remediation_id)
    if rem is None:
        raise HTTPException(404, "remediation not found")
    return remediation_to_dict(rem)


@app.post("/api/remediations/{remediation_id}/execute")
def execute(remediation_id: str, db: Session = Depends(get_db)) -> dict:
    outcome = execute_remediation(db, remediation_id)
    if outcome.status == "not_found":
        raise HTTPException(404, outcome.result)
    return {"status": outcome.status, "result": outcome.result, "executed": outcome.executed}


@app.post("/api/incidents/{incident_id}/verify")
def verify(incident_id: str, db: Session = Depends(get_db)) -> dict:
    rem = db.execute(
        select(Remediation).where(Remediation.incident_id == incident_id,
                                  Remediation.status == "executed")
    ).scalars().first()
    verification = verify_recovery(db, incident_id, rem.id if rem else None)
    if verification is None:
        raise HTTPException(404, "incident not found")
    return verification_to_dict(verification)


@app.get("/api/incidents/{incident_id}/verifications")
def verifications(incident_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(Verification).where(Verification.incident_id == incident_id)).scalars().all()
    return [verification_to_dict(v) for v in rows]


# ---------------- postmortems ----------------

@app.post("/api/incidents/{incident_id}/postmortem")
def create_postmortem(incident_id: str, db: Session = Depends(get_db)) -> dict:
    pm = generate_postmortem(db, incident_id)
    if pm is None:
        raise HTTPException(404, "incident not found")
    return postmortem_to_dict(pm)


@app.get("/api/postmortems")
def list_postmortems(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(Postmortem).order_by(Postmortem.created_at.desc())).scalars().all()
    return [postmortem_to_dict(p) for p in rows]


@app.get("/api/postmortems/{postmortem_id}")
def get_postmortem(postmortem_id: str, db: Session = Depends(get_db)) -> dict:
    pm = db.get(Postmortem, postmortem_id)
    if pm is None:
        raise HTTPException(404, "postmortem not found")
    return postmortem_to_dict(pm)


# ---------------- agent & tools ----------------

@app.get("/api/tools")
def tools(db: Session = Depends(get_db)) -> list[dict]:
    return ToolRegistry(db).list_tools()


@app.get("/api/agent/runs")
def agent_runs(incident_id: str | None = None, db: Session = Depends(get_db)) -> list[dict]:
    stmt = select(AgentRun).order_by(AgentRun.started_at.desc()).limit(50)
    if incident_id:
        stmt = stmt.where(AgentRun.incident_id == incident_id)
    rows = db.execute(stmt).scalars().all()
    return [
        {"id": r.id, "incident_id": r.incident_id, "status": r.status, "provider": r.provider,
         "model": r.model, "started_at": r.started_at, "finished_at": r.finished_at,
         "summary": r.summary, "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
         "llm_request_count": r.llm_request_count, "stop_reason": r.stop_reason}
        for r in rows
    ]


@app.get("/api/agent/runs/{run_id}/trace")
def agent_trace(run_id: str, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(ToolCall).where(ToolCall.run_id == run_id).order_by(ToolCall.seq)).scalars().all()
    return [
        {"seq": t.seq, "tool": t.tool_name, "args": t.args, "status": t.result_status,
         "duration_ms": t.duration_ms, "result_summary": t.result_summary, "error": t.error,
         "created_at": t.created_at}
        for t in rows
    ]


# ---------------- evaluations ----------------

@app.post("/api/evaluations/run")
def evaluations_run(db: Session = Depends(get_db)) -> dict:
    return run_evaluation(db)


@app.get("/api/evaluations")
def evaluations_list(db: Session = Depends(get_db)) -> list[dict]:
    from app.models import EvaluationCase

    rows = db.execute(select(EvaluationCase).order_by(EvaluationCase.created_at.desc())).scalars().all()
    return [
        {"id": r.id, "scenario_id": r.scenario_id, "incident_id": r.incident_id,
         "known_root_cause": r.known_root_cause, "predicted_root_cause": r.predicted_root_cause,
         "root_cause_correct": r.root_cause_correct, "affected_services_correct": r.affected_services_correct,
         "remediation_correct": r.remediation_correct, "recovery_verified": r.recovery_verified,
         "evidence_count": r.evidence_count, "score": r.score}
        for r in rows
    ]


# ---------------- settings ----------------

@app.get("/api/settings", response_model=SettingsOut)
def get_settings_endpoint() -> SettingsOut:
    s = get_settings()
    return SettingsOut(
        llm_provider="openai-compatible" if s.llm_enabled else "mock",
        llm_model=s.llm_model,
        llm_enabled=s.llm_enabled,
        remediation_mode=s.remediation_mode,
        demo_mode=not s.llm_enabled,
        agent_max_tool_calls=s.agent_max_tool_calls,
    )


# ---------------- overview ----------------

@app.get("/api/overview")
def overview(db: Session = Depends(get_db)) -> dict:
    """Aggregated dashboard data - all values computed from stored telemetry."""
    active = db.execute(select(Incident).where(Incident.status != "resolved")).scalars().all()
    all_services = db.execute(select(Service)).scalars().all()
    latest = db.execute(select(func.max(TelemetryEvent.timestamp))).scalar()
    affected: set[str] = set()
    for inc in active:
        affected.update(inc.affected_services or [])
    # error-rate + latency snapshot for gateway
    gw_err = query_series(db, "api-gateway", "error_rate")
    gw_lat = query_series(db, "api-gateway", "p95_latency_ms")
    gw_rate = query_series(db, "api-gateway", "request_rate")
    recent_deps = db.execute(
        select(Deployment).order_by(Deployment.timestamp.desc()).limit(5)
    ).scalars().all()
    # count anomalies across all metric pairs
    pairs = db.execute(
        select(TelemetryEvent.service).distinct()
    ).scalars().all()
    from app.models import MetricPoint

    metric_pairs = db.execute(select(MetricPoint.service, MetricPoint.metric_name).distinct()).all()
    anomaly_count = 0
    anomalies_detail: list[dict] = []
    for service, metric in metric_pairs:
        series = query_series(db, service, metric)
        found = detect_anomalies(series, service, metric)
        if found:
            anomaly_count += 1
            anomalies_detail.append(found[0].to_dict())
    return {
        "synthetic": True,
        "environment": settings.environment,
        "llm_enabled": settings.llm_enabled,
        "active_incidents": [incident_to_dict(i) for i in active],
        "active_incident_count": len(active),
        "affected_services": sorted(affected),
        "service_count": len(all_services),
        "gateway": {
            "error_rate": gw_err[-1]["value"] if gw_err else None,
            "p95_latency_ms": gw_lat[-1]["value"] if gw_lat else None,
            "request_rate": gw_rate[-1]["value"] if gw_rate else None,
        },
        "recent_deployments": [
            {"timestamp": d.timestamp, "service": d.service, "version": d.version}
            for d in recent_deps
        ],
        "anomaly_count": anomaly_count,
        "anomalies": anomalies_detail[:8],
        "latest_telemetry_time": latest,
    }
