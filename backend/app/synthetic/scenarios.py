"""Incident scenario engine.

Each scenario is a causal story: a trigger produces primary telemetry changes
in one service, which propagate through the topology producing secondary
effects. Every scenario declares its ground truth so the evaluation engine can
score RCA accuracy without fabricating anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MetricProfile:
    """How one metric of one service evolves over the scenario window."""

    service: str
    metric: str
    baseline: float
    peak: float
    ramp_minutes: int  # minutes from incident start until peak
    recovery_minutes: int = 6  # minutes after remediation to return near baseline


@dataclass
class LogSignal:
    severity: str
    service: str
    event_type: str
    message: str
    offset_minutes: float  # minutes after incident start
    metadata: dict = field(default_factory=dict)


@dataclass
class Scenario:
    scenario_id: str
    title: str
    category: str  # e.g. database_exhaustion, deployment_regression, ...
    trigger: str
    root_service: str
    severity: str  # expected incident severity
    known_root_cause: str
    root_cause_concepts: list[str]  # core concepts a correct RCA must identify
    expected_affected_services: list[str]
    expected_evidence: list[str]
    acceptable_remediations: list[str]
    metrics: list[MetricProfile]
    logs: list[LogSignal]
    deployment: dict | None = None  # if the incident is deployment-related
    recovery_behavior: str = "gradual"

    def peak_offset(self) -> float:
        return max(m.ramp_minutes for m in self.metrics)


def _db_exhaustion_metrics() -> list[MetricProfile]:
    return [
        MetricProfile("orders-db", "db_latency_ms", 45.0, 1800.0, 5),
        MetricProfile("orders-db", "db_connections", 40.0, 100.0, 4),
        MetricProfile("orders-db", "db_slow_queries", 2.0, 60.0, 6),
        MetricProfile("payments-service", "p95_latency_ms", 180.0, 950.0, 6),
        MetricProfile("payments-service", "error_rate", 0.4, 22.0, 7),
        MetricProfile("orders-service", "error_rate", 0.3, 18.0, 8),
        MetricProfile("orders-service", "p95_latency_ms", 220.0, 1200.0, 8),
        MetricProfile("api-gateway", "error_rate", 0.2, 9.5, 9),
        MetricProfile("api-gateway", "p95_latency_ms", 150.0, 890.0, 9),
        MetricProfile("api-gateway", "request_rate", 850.0, 880.0, 10),
        MetricProfile("orders-service", "request_rate", 310.0, 320.0, 10),
        MetricProfile("payments-service", "request_rate", 300.0, 305.0, 10),
    ]


DB_EXHAUSTION = Scenario(
    scenario_id="db_connection_exhaustion",
    title="Database connection pool exhaustion after deployment",
    category="database_exhaustion",
    trigger="Deployment payments-service v2.4.1 lowers pool recycle interval; connections leak under load",
    root_service="orders-db",
    severity="high",
    known_root_cause="orders-db connection pool exhaustion caused by payments-service deployment v2.4.1 leaking connections",
    root_cause_concepts=["orders-db", "connection", "exhaust"],
    expected_affected_services=["orders-db", "payments-service", "orders-service", "api-gateway"],
    expected_evidence=[
        "orders-db db_connections reached pool limit (100/100)",
        "orders-db db_latency_ms rose several minutes before upstream errors",
        "payments-service timeout errors rose after db latency",
        "orders-service depends on payments-service (topology)",
        "deployment of payments-service preceded all anomalies",
    ],
    acceptable_remediations=["rollback_deployment", "increase_connection_pool", "restart_service", "scale_service"],
    metrics=_db_exhaustion_metrics(),
    logs=[
        LogSignal("INFO", "payments-service", "deployment", "Deployment payments-service v2.4.1 completed", -2.0,
                  {"version": "v2.4.1"}),
        LogSignal("WARN", "orders-db", "connection_pool_warning", "Connection pool at 82% capacity", 2.0,
                  {"pool_used": 82}),
        LogSignal("WARN", "orders-db", "connection_pool_warning", "Connection pool at 95% capacity", 3.0,
                  {"pool_used": 95}),
        LogSignal("ERROR", "orders-db", "connection_exhausted", "Connection pool exhausted: 100/100 in use", 4.0,
                  {"pool_used": 100}),
        LogSignal("ERROR", "payments-service", "database_timeout", "Checkout query timed out after 5000ms waiting for connection", 5.0,
                  {"timeout_ms": 5000, "trace_id": "tr-9042"}),
        LogSignal("ERROR", "payments-service", "database_timeout", "Connection acquire timeout for INSERT charge", 6.0,
                  {"timeout_ms": 5000, "trace_id": "tr-9043"}),
        LogSignal("WARN", "orders-service", "dependency_timeout", "Payment call timed out (order 8831)", 7.0,
                  {"dependency": "payments-service", "trace_id": "tr-8831"}),
        LogSignal("ERROR", "orders-service", "order_failed", "Order 8831 failed: payment step error", 8.0,
                  {"trace_id": "tr-8831"}),
        LogSignal("ERROR", "orders-service", "order_failed", "Order 8845 failed: payment step error", 9.0,
                  {"trace_id": "tr-8845"}),
        LogSignal("WARN", "api-gateway", "upstream_error", "5xx rate from orders routes above threshold", 10.0),
        LogSignal("ERROR", "api-gateway", "client_error_spike", "Elevated 5xx responses on /orders and /checkout", 11.0),
    ],
    deployment={
        "service": "payments-service",
        "version": "v2.4.1",
        "commit": "c41f9ab",
        "actor": "ci-system",
        "notes": "Tune connection recycle interval (pool config change)",
    },
)

MEMORY_LEAK = Scenario(
    scenario_id="memory_leak_orders",
    title="Memory leak in orders-service after cache refactor",
    category="memory_leak",
    trigger="orders-service v3.1.0 retains session objects in a module-level cache without eviction",
    root_service="orders-service",
    severity="high",
    known_root_cause="orders-service memory leak: unbounded in-process cache grows until GC pressure and OOM risk degrade latency",
    root_cause_concepts=["orders-service", "memory"],
    expected_affected_services=["orders-service", "api-gateway"],
    expected_evidence=[
        "orders-service memory_mb grows monotonically across the window",
        "orders-service GC pause time increases",
        "orders-service error_rate and p95 latency rise as memory saturates",
        "payments-service metrics remain near baseline",
        "deployment of orders-service v3.1.0 preceded the growth",
    ],
    acceptable_remediations=["rollback_deployment", "restart_service", "scale_service", "clear_cache"],
    metrics=[
        MetricProfile("orders-service", "memory_mb", 420.0, 1950.0, 9),
        MetricProfile("orders-service", "gc_pause_ms", 15.0, 400.0, 8),
        MetricProfile("orders-service", "p95_latency_ms", 220.0, 1400.0, 8),
        MetricProfile("orders-service", "error_rate", 0.3, 12.0, 9),
        MetricProfile("api-gateway", "error_rate", 0.2, 5.0, 10),
        MetricProfile("api-gateway", "p95_latency_ms", 150.0, 720.0, 10),
        MetricProfile("payments-service", "p95_latency_ms", 180.0, 190.0, 10),
        MetricProfile("orders-service", "request_rate", 310.0, 315.0, 10),
    ],
    logs=[
        LogSignal("INFO", "orders-service", "deployment", "Deployment orders-service v3.1.0 completed", -3.0,
                  {"version": "v3.1.0"}),
        LogSignal("INFO", "orders-service", "memory_growth", "Heap usage trending upward: 480MB", 2.0),
        LogSignal("WARN", "orders-service", "memory_pressure", "Heap usage 75% of limit; GC frequency doubling", 5.0),
        LogSignal("WARN", "orders-service", "memory_pressure", "Heap usage 88% of limit", 8.0),
        LogSignal("ERROR", "orders-service", "gc_overload", "Long GC pause 410ms; request threads stalled", 9.0),
        LogSignal("WARN", "api-gateway", "upstream_error", "orders routes returning slow responses", 10.0),
        LogSignal("ERROR", "orders-service", "order_failed", "Order 9102 failed: worker timeout", 11.0),
    ],
    deployment={
        "service": "orders-service",
        "version": "v3.1.0",
        "commit": "ab77de2",
        "actor": "ci-system",
        "notes": "Refactor session cache (new in-process cache)",
    },
)

DEPLOYMENT_REGRESSION = Scenario(
    scenario_id="deployment_regression_auth",
    title="Auth-service deployment regression breaks token validation",
    category="deployment_regression",
    trigger="auth-service v1.9.2 misparses a token header; a fraction of valid tokens are rejected",
    root_service="auth-service",
    severity="critical",
    known_root_cause="auth-service v1.9.2 regression: token validation rejects ~30% of valid tokens",
    root_cause_concepts=["auth-service", "regression"],
    expected_affected_services=["auth-service", "api-gateway"],
    expected_evidence=[
        "auth-service auth_failure_rate jumps immediately after deployment",
        "api-gateway 401 rate rises while downstream services stay healthy",
        "orders/payments latency and error rates remain near baseline",
        "failure starts exactly at deployment time",
    ],
    acceptable_remediations=["rollback_deployment", "disable_feature_flag"],
    metrics=[
        MetricProfile("auth-service", "auth_failure_rate", 0.5, 31.0, 2),
        MetricProfile("auth-service", "error_rate", 0.3, 30.0, 2),
        MetricProfile("auth-service", "p95_latency_ms", 60.0, 65.0, 2),
        MetricProfile("api-gateway", "error_rate", 0.2, 15.0, 3),
        MetricProfile("api-gateway", "http_401_rate", 0.1, 30.0, 3),
        MetricProfile("orders-service", "error_rate", 0.3, 0.4, 5),
        MetricProfile("orders-service", "request_rate", 310.0, 260.0, 3),
        MetricProfile("payments-service", "error_rate", 0.4, 0.5, 5),
    ],
    logs=[
        LogSignal("INFO", "auth-service", "deployment", "Deployment auth-service v1.9.2 completed", -1.0,
                  {"version": "v1.9.2"}),
        LogSignal("WARN", "auth-service", "auth_failure_spike", "Token validation failures elevated", 1.0),
        LogSignal("ERROR", "auth-service", "token_rejected", "Rejected valid-format token (header parse error)", 1.5),
        LogSignal("ERROR", "auth-service", "token_rejected", "Rejected valid-format token (header parse error)", 2.5),
        LogSignal("WARN", "api-gateway", "upstream_error", "401 rate from auth backend above threshold", 3.0),
        LogSignal("ERROR", "api-gateway", "client_error_spike", "Elevated 401 responses on all routes", 4.0),
    ],
    deployment={
        "service": "auth-service",
        "version": "v1.9.2",
        "commit": "de90c33",
        "actor": "ci-system",
        "notes": "Token header parsing change",
    },
)

CACHE_FAILURE = Scenario(
    scenario_id="cache_failure_inventory",
    title="Inventory cache failure pushes load to inventory-db",
    category="cache_failure",
    trigger="inventory-service Redis cache cluster fails; all reads fall through to inventory-db",
    root_service="inventory-service",
    severity="medium",
    known_root_cause="inventory-service cache outage: cache hit rate collapses and inventory-db read load multiplies",
    root_cause_concepts=["inventory", "cache"],
    expected_affected_services=["inventory-service", "inventory-db", "orders-service", "api-gateway"],
    expected_evidence=[
        "inventory-service cache_hit_rate collapses from ~92% to near zero",
        "inventory-db read latency and CPU rise sharply",
        "orders-service dependency timeouts on inventory calls follow",
        "topology: orders-service depends on inventory-service",
    ],
    acceptable_remediations=["restart_service", "clear_cache", "scale_service"],
    metrics=[
        MetricProfile("inventory-service", "cache_hit_rate", 92.0, 3.0, 1),
        MetricProfile("inventory-service", "p95_latency_ms", 45.0, 380.0, 3),
        MetricProfile("inventory-db", "db_latency_ms", 12.0, 210.0, 2),
        MetricProfile("inventory-db", "cpu_percent", 30.0, 93.0, 3),
        MetricProfile("inventory-service", "error_rate", 0.2, 8.0, 4),
        MetricProfile("orders-service", "error_rate", 0.3, 7.0, 5),
        MetricProfile("orders-service", "p95_latency_ms", 220.0, 600.0, 5),
        MetricProfile("api-gateway", "error_rate", 0.2, 3.5, 6),
    ],
    logs=[
        LogSignal("ERROR", "inventory-service", "cache_unavailable", "Redis cluster unreachable; connection refused", 0.5),
        LogSignal("WARN", "inventory-service", "cache_fallback", "Reads falling through to inventory-db", 1.0),
        LogSignal("WARN", "inventory-db", "load_spike", "Read QPS 6x baseline after cache loss", 2.0),
        LogSignal("ERROR", "inventory-service", "dependency_timeout", "DB read timed out under load", 3.5),
        LogSignal("WARN", "orders-service", "dependency_timeout", "Inventory reservation slow (order 7712)", 5.0),
        LogSignal("WARN", "api-gateway", "upstream_error", "Inventory-dependent routes degraded", 6.0),
    ],
)

DEPENDENCY_TIMEOUT = Scenario(
    scenario_id="dependency_timeout_email",
    title="External email provider latency cascades into notification backlog",
    category="dependency_timeout",
    trigger="external-email-provider applies rate limits; latency rises to 8s per send",
    root_service="external-email-provider",
    severity="medium",
    known_root_cause="external-email-provider rate limiting: per-send latency rises until notification-service exhausts its worker pool",
    root_cause_concepts=["email-provider", "rate limit"],
    expected_affected_services=["notification-service", "external-email-provider", "orders-service", "api-gateway"],
    expected_evidence=[
        "external-email-provider send latency rises first",
        "notification-service queue depth and p95 latency grow",
        "orders-service latency rises on the notification step (non-critical dependency)",
        "orders completion rate dips but errors stay moderate",
    ],
    acceptable_remediations=["restart_service", "disable_feature_flag", "scale_service"],
    metrics=[
        MetricProfile("external-email-provider", "send_latency_ms", 250.0, 8000.0, 4),
        MetricProfile("external-email-provider", "send_error_rate", 0.5, 18.0, 5),
        MetricProfile("notification-service", "queue_depth", 4.0, 900.0, 5),
        MetricProfile("notification-service", "p95_latency_ms", 300.0, 7500.0, 6),
        MetricProfile("orders-service", "p95_latency_ms", 220.0, 800.0, 7),
        MetricProfile("orders-service", "error_rate", 0.3, 2.0, 8),
        MetricProfile("api-gateway", "p95_latency_ms", 150.0, 400.0, 8),
    ],
    logs=[
        LogSignal("WARN", "external-email-provider", "rate_limited", "Provider throttling requests (429 responses)", 1.0),
        LogSignal("WARN", "notification-service", "send_slow", "Average send latency above 5s", 3.0),
        LogSignal("WARN", "notification-service", "queue_backlog", "Notification queue depth growing: 400+", 5.0),
        LogSignal("ERROR", "notification-service", "send_failed", "Send aborted after 3 retries", 6.5),
        LogSignal("WARN", "orders-service", "dependency_timeout", "Notification step slow (order 6641)", 7.5),
        LogSignal("WARN", "api-gateway", "upstream_error", "Checkout completion latency degraded", 8.5),
    ],
)

SCENARIOS: dict[str, Scenario] = {
    s.scenario_id: s for s in [DB_EXHAUSTION, MEMORY_LEAK, DEPLOYMENT_REGRESSION, CACHE_FAILURE, DEPENDENCY_TIMEOUT]
}

# Benchmark set used by the evaluation engine (docs/EVALUATION.md).
EVALUATION_SCENARIOS = [DB_EXHAUSTION, DEPLOYMENT_REGRESSION, CACHE_FAILURE, MEMORY_LEAK, DEPENDENCY_TIMEOUT]
