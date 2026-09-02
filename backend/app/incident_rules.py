"""Incident correlation engine: deterministic rules over correlated evidence.

Rules produce candidate incidents from metric anomalies + logs + topology +
deployments. The AI investigator reasons on TOP of these structured facts -
it never invents incidents from scratch.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.metrics_engine import detect_anomalies, query_series
from app.models import Deployment, MetricPoint, TelemetryEvent
from app.topology_engine import load_topology


@dataclass
class RuleResult:
    rule_name: str
    category: str
    severity: str
    confidence: float
    primary_service: str
    affected_services: list[str]
    signals: list[dict] = field(default_factory=list)
    evidence_hints: list[str] = field(default_factory=list)
    explanation: str = ""


class CorrelationRule:
    """Base rule: subclasses set class attributes; no dataclass fields needed."""

    name: str = ""
    category: str = ""
    severity: str = ""
    description: str = ""

    def evaluate(self, ctx: CorrelationContext) -> "RuleResult | None":
        raise NotImplementedError


class CorrelationContext:
    """Everything a rule may look at. Deterministic, DB-backed."""

    def __init__(self, db: Session, window_minutes: int = 30):
        self.db = db
        self.window = window_minutes
        self.topology = load_topology(db)
        self._anomalies: list[dict] | None = None
        self._recent_deployments: list[Deployment] | None = None

    def anomalies(self) -> list[dict]:
        if self._anomalies is not None:
            return self._anomalies
        out: list[dict] = []
        pairs = self.db.execute(
            select(MetricPoint.service, MetricPoint.metric_name).distinct()
        ).all()
        for service, metric in pairs:
            series = query_series(self.db, service, metric)
            for anomaly in detect_anomalies(series, service, metric):
                out.append(anomaly.to_dict())
        self._anomalies = out
        return out

    def error_logs(self, minutes: int | None = None) -> list[TelemetryEvent]:
        latest = self.db.execute(select(MetricPoint.timestamp).order_by(MetricPoint.timestamp.desc())).scalar()
        cutoff = (latest or datetime.now(timezone.utc)) - timedelta(minutes=minutes or self.window)
        stmt = select(TelemetryEvent).where(
            and_(TelemetryEvent.severity.in_(["ERROR", "CRITICAL"]), TelemetryEvent.timestamp >= cutoff)
        ).order_by(TelemetryEvent.timestamp)
        return list(self.db.execute(stmt).scalars().all())

    def deployments(self, minutes: int | None = None) -> list[Deployment]:
        if self._recent_deployments is not None and minutes is None:
            return self._recent_deployments
        latest = self.db.execute(select(Deployment.timestamp).order_by(Deployment.timestamp.desc())).scalar()
        cutoff = (latest or datetime.now(timezone.utc)) - timedelta(minutes=minutes or 24 * 60)
        stmt = select(Deployment).where(Deployment.timestamp >= cutoff).order_by(Deployment.timestamp)
        rows = list(self.db.execute(stmt).scalars().all())
        if minutes is None:
            self._recent_deployments = rows
        return rows


def _matching_anomaly(anomalies: list[dict], service: str, metric: str) -> dict | None:
    for a in anomalies:
        if a["service"] == service and a["metric"] == metric:
            return a
    return None


class DatabaseExhaustionRule(CorrelationRule):
    name = "database_connection_exhaustion"
    category = "database_exhaustion"
    severity = "high"
    description = "DB latency/connections rise with upstream timeout/failure errors"

    def evaluate(self, ctx: CorrelationContext) -> RuleResult | None:
        anomalies = ctx.anomalies()
        db_services = [
            n for n, info in ctx.topology.nodes.items() if info.get("kind") == "database"
        ]
        for db_svc in db_services:
            latency = _matching_anomaly(anomalies, db_svc, "db_latency_ms")
            connections = _matching_anomaly(anomalies, db_svc, "db_connections")
            if not latency:
                continue
            signals = [latency]
            evidence = [latency["explanation"]]
            confidence = 0.55
            if connections:
                signals.append(connections)
                evidence.append(connections["explanation"])
                confidence += 0.2
            # upstream error logs
            err_logs = [
                l for l in ctx.error_logs()
                if l.service in ctx.topology.upstream(db_svc) or l.service == db_svc
            ]
            timeout_logs = [l for l in err_logs if "timeout" in (l.message or "").lower() or "exhaust" in (l.message or "").lower()]
            if timeout_logs:
                confidence += 0.15
                evidence.append(
                    f"{len(timeout_logs)} timeout/exhaustion ERROR logs from services depending on {db_svc}"
                )
            affected = ctx.topology.impact_radius(db_svc)
            if confidence < 0.6:
                continue
            return RuleResult(
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                confidence=round(min(confidence, 0.95), 2),
                primary_service=db_svc,
                affected_services=affected,
                signals=[
                    {"kind": "metric", "service": s["service"], "metric": s["metric"],
                     "value": s["value"], "baseline": s["baseline"], "explanation": s["explanation"]}
                    for s in signals
                ],
                evidence_hints=evidence,
                explanation=f"{db_svc} shows capacity/exhaustion anomalies with correlated upstream failures",
            )
        return None


class DeploymentRegressionRule(CorrelationRule):
    name = "deployment_regression"
    category = "deployment_regression"
    severity = "high"
    description = "Errors jump immediately after a deployment of the affected service"

    def evaluate(self, ctx: CorrelationContext) -> RuleResult | None:
        anomalies = ctx.anomalies()
        for dep in ctx.deployments(minutes=120):
            svc_anomalies = [a for a in anomalies if a["service"] == dep.service and a["z_score"] > 0]
            if not svc_anomalies:
                continue
            err_logs = [l for l in ctx.error_logs() if l.service == dep.service]
            if not err_logs and not svc_anomalies:
                continue
            confidence = 0.5 + min(0.3, 0.1 * len(svc_anomalies))
            if err_logs:
                confidence += 0.1
            # verify errors started AFTER deployment
            first_anomaly_ts = min(a["timestamp"] for a in svc_anomalies)
            if isinstance(first_anomaly_ts, str):
                first_anomaly_ts = datetime.fromisoformat(first_anomaly_ts)
            if first_anomaly_ts < dep.timestamp:
                confidence -= 0.25
            return RuleResult(
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                confidence=round(min(confidence, 0.95), 2),
                primary_service=dep.service,
                affected_services=ctx.topology.impact_radius(dep.service),
                signals=[
                    {"kind": "deployment", "service": dep.service, "version": dep.version,
                     "deployed_at": dep.timestamp.isoformat()}
                ] + [
                    {"kind": "metric", "service": a["service"], "metric": a["metric"],
                     "explanation": a["explanation"]} for a in svc_anomalies[:4]
                ],
                evidence_hints=[
                    f"Deployment of {dep.service} {dep.version} at {dep.timestamp.isoformat()} preceded anomalies",
                    *[a["explanation"] for a in svc_anomalies[:4]],
                ],
                explanation=f"{dep.service} degraded immediately after deployment {dep.version}",
            )
        return None


class ResourceSaturationRule(CorrelationRule):
    name = "resource_saturation"
    category = "resource_saturation"
    severity = "high"
    description = "Memory/CPU saturation with degrading latency and rising errors"

    def evaluate(self, ctx: CorrelationContext) -> RuleResult | None:
        anomalies = ctx.anomalies()
        for svc in ctx.topology.nodes:
            mem = _matching_anomaly(anomalies, svc, "memory_mb")
            cpu = _matching_anomaly(anomalies, svc, "cpu_percent")
            gc = _matching_anomaly(anomalies, svc, "gc_pause_ms")
            if not mem and not cpu:
                continue
            signals = [s for s in (mem, cpu, gc) if s]
            confidence = 0.5 + 0.15 * len(signals)
            latency = _matching_anomaly(anomalies, svc, "p95_latency_ms")
            if latency:
                signals.append(latency)
                confidence += 0.1
            return RuleResult(
                rule_name=self.name,
                category="memory_leak" if mem else "resource_saturation",
                severity=self.severity,
                confidence=round(min(confidence, 0.95), 2),
                primary_service=svc,
                affected_services=ctx.topology.impact_radius(svc),
                signals=[
                    {"kind": "metric", "service": s["service"], "metric": s["metric"],
                     "explanation": s["explanation"]} for s in signals
                ],
                evidence_hints=[s["explanation"] for s in signals],
                explanation=f"{svc} shows resource saturation with correlated latency degradation",
            )
        return None


class CacheFailureRule(CorrelationRule):
    name = "cache_failure"
    category = "cache_failure"
    severity = "medium"
    description = "Cache hit rate collapse with DB load increase downstream"

    def evaluate(self, ctx: CorrelationContext) -> RuleResult | None:
        anomalies = ctx.anomalies()
        for svc in ctx.topology.nodes:
            cache = _matching_anomaly(anomalies, svc, "cache_hit_rate")
            if not cache or cache["z_score"] > 0:
                continue  # cache hit must DECREASE
            signals = [cache]
            evidence = [cache["explanation"]]
            confidence = 0.5
            db_deps = ctx.topology.downstream(svc)
            for db_dep in db_deps:
                db_latency = _matching_anomaly(anomalies, db_dep, "db_latency_ms")
                db_cpu = _matching_anomaly(anomalies, db_dep, "cpu_percent")
                for a in (db_latency, db_cpu):
                    if a:
                        signals.append(a)
                        evidence.append(a["explanation"])
                        confidence += 0.15
            return RuleResult(
                rule_name=self.name,
                category=self.category,
                severity=self.severity,
                confidence=round(min(confidence, 0.95), 2),
                primary_service=svc,
                affected_services=ctx.topology.impact_radius(svc),
                signals=[
                    {"kind": "metric", "service": s["service"], "metric": s["metric"],
                     "explanation": s["explanation"]} for s in signals
                ],
                evidence_hints=evidence,
                explanation=f"{svc} cache hit rate collapsed; backing store load increased",
            )
        return None


class DependencyTimeoutRule(CorrelationRule):
    name = "dependency_timeout"
    category = "dependency_timeout"
    severity = "medium"
    description = "A dependency's latency rises before its dependents degrade"

    def evaluate(self, ctx: CorrelationContext) -> RuleResult | None:
        anomalies = ctx.anomalies()
        # find the earliest latency anomaly across all services
        latency_anoms = [a for a in anomalies if "latency" in a["metric"]]
        if not latency_anoms:
            return None
        earliest = min(latency_anoms, key=lambda a: a["timestamp"])
        root = earliest["service"]
        dependents = ctx.topology.upstream(root)
        if not dependents:
            return None
        corroborated = [a for a in anomalies if a["service"] in dependents and a["service"] != root]
        confidence = 0.5 + min(0.3, 0.1 * len(corroborated))
        return RuleResult(
            rule_name=self.name,
            category=self.category,
            severity=self.severity,
            confidence=round(min(confidence, 0.95), 2),
            primary_service=root,
            affected_services=ctx.topology.impact_radius(root),
            signals=[
                {"kind": "metric", "service": earliest["service"], "metric": earliest["metric"],
                 "explanation": earliest["explanation"]}
            ] + [
                {"kind": "metric", "service": a["service"], "metric": a["metric"],
                 "explanation": a["explanation"]} for a in corroborated[:4]
            ],
            evidence_hints=[
                f"{earliest['service']}/{earliest['metric']} degraded earliest ({earliest['explanation']})",
                f"Topology: {', '.join(dependents)} depend on {root}",
            ],
            explanation=f"{root} degraded first; dependents followed - consistent with dependency timeout",
        )


DEFAULT_RULES: list[CorrelationRule] = [
    DatabaseExhaustionRule(),
    DeploymentRegressionRule(),
    ResourceSaturationRule(),
    CacheFailureRule(),
    DependencyTimeoutRule(),
]


def run_correlation(db: Session, window_minutes: int = 30) -> list[RuleResult]:
    """Run all rules; return results sorted by confidence."""
    ctx = CorrelationContext(db, window_minutes=window_minutes)
    results = []
    for rule in DEFAULT_RULES:
        try:
            result = rule.evaluate(ctx)
        except Exception:
            continue
        if result is not None:
            results.append(result)
    results.sort(key=lambda r: r.confidence, reverse=True)
    return results
