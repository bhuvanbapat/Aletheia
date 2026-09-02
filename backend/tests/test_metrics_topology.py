"""Unit tests: metrics engine (aggregation, baseline, anomalies) + topology."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.metrics_engine import compute_baseline, detect_anomalies, ewma
from app.synthetic.topology import build_default_topology


def _series(baseline: float, spike: float, n_base: int = 60, n_spike: int = 6):
    start = datetime(2026, 9, 1, 12, 0, 0)
    points = [
        {"timestamp": start + timedelta(minutes=i), "value": baseline + (i % 3)}
        for i in range(n_base)
    ]
    points += [
        {"timestamp": start + timedelta(minutes=n_base + i), "value": spike}
        for i in range(n_spike)
    ]
    return points


def test_baseline_computed_from_values():
    series = _series(40.0, 40.0)
    b = compute_baseline(series)
    assert b is not None
    assert b["n"] == 66
    assert 39 <= b["mean"] <= 42


def test_detect_anomaly_on_spike():
    series = _series(40.0, 98.0)
    anomalies = detect_anomalies(series, "orders-db", "db_connections")
    assert len(anomalies) == 1
    a = anomalies[0]
    assert a.z_score > 3
    # explanation must contain actual values, not fabricated
    assert "40" in a.explanation or "41" in a.explanation
    assert "98" in a.explanation
    assert "z=" in a.explanation


def test_no_anomaly_on_stable_series():
    series = _series(40.0, 41.0)
    anomalies = detect_anomalies(series, "svc", "metric")
    assert anomalies == []


def test_ewma_smoothing():
    values = [0, 100, 0, 100]
    smoothed = ewma(values, alpha=0.5)
    assert smoothed[0] == 0
    assert smoothed[1] == 50
    assert smoothed[2] == 25
    assert smoothed[3] == 62.5


def test_detects_decreasing_anomaly():
    series = _series(92.0, 3.0)  # cache hit rate collapse
    anomalies = detect_anomalies(series, "inventory-service", "cache_hit_rate")
    assert len(anomalies) == 1
    assert anomalies[0].z_score < 0  # decrease = negative z


# ---------------- topology ----------------

def test_topology_downstream_and_upstream():
    topo = build_default_topology()
    assert "payments-service" in topo.downstream("orders-service")
    assert "orders-db" in topo.downstream("payments-service")
    assert "orders-service" in topo.upstream("payments-service")


def test_topology_impact_radius_propagates():
    topo = build_default_topology()
    # orders-db degraded -> payments, orders, gateway affected
    impacted = topo.impact_radius("orders-db")
    assert "payments-service" in impacted
    assert "orders-service" in impacted
    assert "api-gateway" in impacted
    assert "orders-db" in impacted


def test_topology_descendants():
    topo = build_default_topology()
    assert topo.descendants("orders-service") == sorted({
        "payments-service", "inventory-service", "notification-service",
        "orders-db", "inventory-db", "external-email-provider",
    })


def test_propagation_path_stages():
    topo = build_default_topology()
    path = topo.propagation_path("orders-db")
    stages = [p["stage"] for p in path]
    assert stages == ["root", "direct_impact", "downstream_impact", "user_impact"]
    root = path[0]
    assert root["services"] == ["orders-db"]
    direct = path[1]
    assert "payments-service" in direct["services"]
