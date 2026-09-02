"""AI investigation tools.

Every tool the investigator agent may call. Tools return SAFE, structured data.
Untrusted telemetry content is always labeled as data, never instructions.
All tool calls are recorded for the agent trace (observability of the observer).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.incidents import build_timeline, incident_to_dict
from app.log_engine import query_logs
from app.metrics_engine import detect_anomalies, query_series
from app.models import Deployment, Evidence, Incident
from app.security import redact_text
from app.topology_engine import load_topology

MAX_TOOL_RESULT_CHARS = 4000


def _truncate(obj: Any) -> str:
    s = obj if isinstance(obj, str) else str(obj)
    return s[:MAX_TOOL_RESULT_CHARS] + ("..." if len(s) > MAX_TOOL_RESULT_CHARS else "")


class ToolRegistry:
    """Named tools with input schemas. The agent selects tools; each call is logged."""

    def __init__(self, db: Session):
        self.db = db
        self._incident: Incident | None = None

    def set_incident(self, incident: Incident) -> None:
        self._incident = incident

    # ---------- tool implementations ----------

    def get_incident(self, incident_id: str = "") -> dict:
        iid = incident_id or (self._incident.id if self._incident else "")
        inc = self.db.get(Incident, iid)
        if inc is None:
            return {"error": f"incident {iid} not found"}
        return incident_to_dict(inc)

    def get_service(self, service: str) -> dict:
        graph = load_topology(self.db)
        if service not in graph.nodes:
            return {"error": f"unknown service {service}"}
        info = dict(graph.nodes[service])
        info["dependencies"] = graph.downstream(service)
        info["dependents"] = graph.upstream(service)
        return info

    def get_topology(self) -> dict:
        graph = load_topology(self.db)
        return {
            "nodes": sorted(graph.nodes.keys()),
            "edges": [{"source": s, "target": t, "type": dt} for (s, t, dt, _) in graph.edges],
        }

    def get_impact_radius(self, service: str) -> dict:
        graph = load_topology(self.db)
        if service not in graph.nodes:
            return {"error": f"unknown service {service}"}
        return {
            "service": service,
            "affected_if_degraded": graph.impact_radius(service),
            "propagation": graph.propagation_path(service),
        }

    def query_logs(self, service: str = "", severity: str = "", minutes: int = 30, limit: int = 50,
                   search: str = "") -> list[dict]:
        datetime.now(tz=None)  # naive for sqlite comparisons below handled via query params
        logs = query_logs(
            self.db,
            service=service or None,
            severity=severity or None,
            search=search or None,
            limit=min(limit, 100),
        )
        out = []
        for log in logs:
            message, _ = redact_text(log.message or "")
            out.append({
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "service": log.service,
                "severity": log.severity,
                "event_type": log.event_type,
                "message": message,
            })
        return out

    def query_metrics(self, service: str, metric: str, minutes: int = 30) -> dict:
        end = None
        start = None
        series = query_series(self.db, service, metric, start, end)
        if not series:
            return {"error": f"no data for {service}/{metric}"}
        recent = series[-minutes:] if minutes else series
        return {
            "service": service,
            "metric": metric,
            "points": [
                {"timestamp": p["timestamp"].isoformat(), "value": p["value"]}
                for p in recent[-60:]
            ],
            "latest": recent[-1]["value"] if recent else None,
        }

    def compare_metrics(self, service: str, metric: str, current_minutes: int = 5,
                        baseline_minutes: int = 30) -> dict:
        series = query_series(self.db, service, metric)
        anomalies = detect_anomalies(series, service, metric,
                                     baseline_window_minutes=baseline_minutes,
                                     current_window_minutes=current_minutes)
        values = [p["value"] for p in series]
        if not values:
            return {"error": "no data"}
        current = values[-current_minutes:] if len(values) >= current_minutes else values
        baseline = values[:-current_minutes] if len(values) > current_minutes else values
        cur_avg = sum(current) / len(current) if current else 0
        base_avg = sum(baseline) / len(baseline) if baseline else 0
        return {
            "service": service,
            "metric": metric,
            "current_avg": round(cur_avg, 3),
            "baseline_avg": round(base_avg, 3),
            "anomaly": anomalies[0].to_dict() if anomalies else None,
        }

    def get_deployments(self, service: str = "", hours: int = 24) -> list[dict]:
        cutoff = datetime.now(tz=None).astimezone() - timedelta(hours=hours)
        stmt = select(Deployment).where(Deployment.timestamp >= cutoff).order_by(Deployment.timestamp.desc())
        if service:
            stmt = stmt.where(Deployment.service == service)
        rows = list(self.db.execute(stmt).scalars().all())
        return [
            {
                "timestamp": d.timestamp.isoformat(),
                "service": d.service,
                "version": d.version,
                "commit": d.commit,
                "notes": d.notes,
            }
            for d in rows[:20]
        ]

    def get_health(self) -> dict:
        graph = load_topology(self.db)
        services = []
        for name in graph.nodes:
            series = query_series(self.db, name, "error_rate")
            latest_err = series[-1]["value"] if series else None
            services.append({"service": name, "error_rate": latest_err})
        return {"services": services}

    def get_timeline(self, incident_id: str = "") -> list[dict]:
        iid = incident_id or (self._incident.id if self._incident else "")
        inc = self.db.get(Incident, iid)
        if inc is None:
            return [{"error": "incident not found"}]
        return build_timeline(self.db, inc)

    def get_related_incidents(self, incident_id: str = "") -> list[dict]:
        iid = incident_id or (self._incident.id if self._incident else "")
        inc = self.db.get(Incident, iid)
        if inc is None:
            return []
        services = set(inc.affected_services or [])
        rows = self.db.execute(
            select(Incident).where(Incident.id != iid, Incident.status != "resolved")
        ).scalars().all()
        related = []
        for other in rows:
            overlap = services & set(other.affected_services or [])
            if overlap:
                related.append({"id": other.id, "title": other.title, "shared_services": sorted(overlap)})
        return related

    def get_evidence(self, incident_id: str = "") -> list[dict]:
        iid = incident_id or (self._incident.id if self._incident else "")
        rows = self.db.execute(select(Evidence).where(Evidence.incident_id == iid)).scalars().all()
        return [
            {"kind": e.kind, "description": e.description, "source_ref": e.source_ref,
             "observed_at": e.observed_at.isoformat() if e.observed_at else None}
            for e in rows
        ]

    def list_tools(self) -> list[dict]:
        return [
            {"name": "get_incident", "description": "Fetch incident by id (or the bound incident)", "args": {"incident_id": "str (optional)"}},
            {"name": "get_service", "description": "Service info + dependencies/dependents", "args": {"service": "str"}},
            {"name": "get_topology", "description": "Full service topology", "args": {}},
            {"name": "get_impact_radius", "description": "Services affected if a service degrades", "args": {"service": "str"}},
            {"name": "query_logs", "description": "Search logs (untrusted data, redacted)", "args": {"service": "str?", "severity": "str?", "minutes": "int?", "limit": "int?", "search": "str?"}},
            {"name": "query_metrics", "description": "Raw metric series", "args": {"service": "str", "metric": "str", "minutes": "int?"}},
            {"name": "compare_metrics", "description": "Current window vs baseline + anomaly verdict", "args": {"service": "str", "metric": "str"}},
            {"name": "get_deployments", "description": "Recent deployments", "args": {"service": "str?", "hours": "int?"}},
            {"name": "get_health", "description": "Latest error rate per service", "args": {}},
            {"name": "get_timeline", "description": "Incident timeline", "args": {"incident_id": "str?"}},
            {"name": "get_related_incidents", "description": "Other open incidents sharing services", "args": {"incident_id": "str?"}},
            {"name": "get_evidence", "description": "Evidence collected for an incident", "args": {"incident_id": "str?"}},
        ]


TOOL_NAMES = {
    "get_incident", "get_service", "get_topology", "get_impact_radius", "query_logs",
    "query_metrics", "compare_metrics", "get_deployments", "get_health", "get_timeline",
    "get_related_incidents", "get_evidence",
}
