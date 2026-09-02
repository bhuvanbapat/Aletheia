"""Demo bootstrap: seed the synthetic environment and (optionally) run one
flagship incident end-to-end so the app is immediately explorable."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion import ingest_events, ingest_metric_points
from app.models import Deployment as DeploymentModel
from app.models import Environment, Incident
from app.synthetic.generator import generate_baseline_window, generate_incident_window
from app.synthetic.scenarios import DB_EXHAUSTION
from app.topology_engine import seed_default_topology


def bootstrap_demo(db: Session, run_flagship_incident: bool = True) -> dict:
    """Idempotent seeding. Returns summary of what was created."""
    summary: dict = {"services": 0, "events": 0, "metric_points": 0, "deployments": 0, "incident": None}
    seed_default_topology(db)
    services = db.execute(select(Environment)).scalars().all()
    summary["services"] = len(services)

    if run_flagship_incident:
        # check whether the flagship incident already exists
        existing = db.execute(
            select(Incident).where(Incident.scenario_id == DB_EXHAUSTION.scenario_id)
        ).scalars().first()
        if existing is None:
            base_start = datetime.now(UTC) - timedelta(minutes=50)
            base_events, base_metrics = generate_baseline_window(base_start, minutes=30, seed=7)
            ingest_events(db, base_events, batch_id="demo-baseline")
            ingest_metric_points(db, base_metrics)
            incident_start = base_start + timedelta(minutes=35)
            inc_events, inc_metrics, deployments = generate_incident_window(
                DB_EXHAUSTION, incident_start, duration_minutes=15, seed=7
            )
            ingest_events(db, inc_events, batch_id="demo-incident")
            ingest_metric_points(db, inc_metrics)
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
            summary["events"] = len(base_events) + len(inc_events)
            summary["metric_points"] = len(base_metrics) + len(inc_metrics)
            summary["deployments"] = len(deployments)

            # create the incident directly from the scenario (deterministic demo path)
            incident = Incident(
                id=f"INC-{uuid.uuid4().hex[:8].upper()}",
                title=DB_EXHAUSTION.title,
                status="open",
                severity=DB_EXHAUSTION.severity,
                confidence=0.0,
                category=DB_EXHAUSTION.category,
                started_at=incident_start,
                detected_at=datetime.now(UTC),
                affected_services=list(DB_EXHAUSTION.expected_affected_services),
                signals=[
                    {"kind": "metric", "service": p.service, "metric": p.metric}
                    for p in DB_EXHAUSTION.metrics[:6]
                ],
                scenario_id=DB_EXHAUSTION.scenario_id,
            )
            db.add(incident)
            db.commit()
            summary["incident"] = incident.id
    return summary
