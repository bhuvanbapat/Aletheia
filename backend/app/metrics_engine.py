"""Metric engine: querying, aggregation, baselines, anomaly detection.

Interpretable methods only: rolling mean/stddev, z-score, EWMA, rate-of-change,
threshold. Every anomaly carries a human-readable explanation with real values
(no fabricated baselines).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import MetricPoint


@dataclass
class Anomaly:
    service: str
    metric: str
    timestamp: datetime
    value: float
    baseline: float
    z_score: float
    method: str
    explanation: str

    def to_dict(self) -> dict:
        return asdict(self)


def query_series(
    db: Session,
    service: str,
    metric: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict]:
    """Raw series points sorted by time."""
    stmt = select(MetricPoint).where(
        and_(MetricPoint.service == service, MetricPoint.metric_name == metric)
    )
    if start:
        stmt = stmt.where(MetricPoint.timestamp >= start)
    if end:
        stmt = stmt.where(MetricPoint.timestamp <= end)
    stmt = stmt.order_by(MetricPoint.timestamp)
    rows = db.execute(stmt).scalars().all()
    return [{"timestamp": r.timestamp, "value": r.value} for r in rows]


def compute_baseline(series: list[dict], window_minutes: int = 30) -> dict | None:
    """Mean/stddev/min/max over the (older) portion of the series."""
    if not series:
        return None
    values = [p["value"] for p in series]
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / max(1, n - 1)
    return {"mean": mean, "stddev": var**0.5, "min": min(values), "max": max(values), "n": n}


def detect_anomalies(
    series: list[dict],
    service: str,
    metric: str,
    baseline_window_minutes: int = 60,
    current_window_minutes: int = 5,
    z_threshold: float = 3.0,
    ewma_alpha: float = 0.3,
) -> list[Anomaly]:
    """Detect anomalies in the most recent window vs a rolling baseline.

    The baseline window is intentionally long (default 60m) so that a
    gradually-developing incident does not dilute its own baseline: the
    majority of the window is pre-incident steady-state.
    Explanation strings always include actual baseline and current values.
    """
    if len(series) < 10:
        return []
    end = series[-1]["timestamp"]
    current_start = end - timedelta(minutes=current_window_minutes)
    baseline_start = end - timedelta(minutes=baseline_window_minutes + current_window_minutes)

    baseline_points = [p for p in series if baseline_start <= p["timestamp"] < current_start]
    current_points = [p for p in series if p["timestamp"] >= current_start]
    if not baseline_points or not current_points:
        # fall back: split series in half
        mid = len(series) // 2
        baseline_points, current_points = series[:mid], series[mid:]

    # Robust baseline (Iglewicz-Hoaglin modified z-score): median + MAD scaled
    # to a stddev-equivalent. Robust to a developing incident polluting the
    # tail of its own baseline window, unlike mean/stddev.
    b_values = sorted(p["value"] for p in baseline_points)
    median = b_values[len(b_values) // 2]
    abs_devs = sorted(abs(v - median) for v in b_values)
    mad = abs_devs[len(abs_devs) // 2]
    robust_sigma = max(mad * 1.4826, 1e-9)

    current_mean = sum(p["value"] for p in current_points) / len(current_points)
    z = (current_mean - median) / robust_sigma
    anomalies: list[Anomaly] = []
    base_mean = median
    if abs(z) >= z_threshold:
        direction = "increased" if z > 0 else "decreased"
        pct = abs(current_mean - base_mean) / max(1e-9, abs(base_mean)) * 100
        explanation = (
            f"{service}/{metric} {direction} from {base_mean:.1f} baseline to {current_mean:.1f} "
            f"(z={z:.2f}, {pct:.0f}% change over last {current_window_minutes}m vs prior "
            f"{baseline_window_minutes}m baseline)"
        )
        anomalies.append(
            Anomaly(
                service=service,
                metric=metric,
                timestamp=current_points[-1]["timestamp"],
                value=round(current_mean, 3),
                baseline=round(base_mean, 3),
                z_score=round(z, 2),
                method="modified-z-score",
                explanation=explanation,
            )
        )
    return anomalies


def ewma(values: list[float], alpha: float = 0.3) -> list[float]:
    out: list[float] = []
    prev = values[0] if values else 0.0
    for v in values:
        prev = alpha * v + (1 - alpha) * prev
        out.append(prev)
    return out


def summarize_service_metrics(db: Session, service: str, window_minutes: int = 15) -> dict:
    """Latest values + change vs previous window for each metric of a service."""
    now = db.execute(select(func.max(MetricPoint.timestamp))).scalar()
    stmt = select(MetricPoint.metric_name).where(MetricPoint.service == service).distinct()
    metric_names = [m for (m,) in db.execute(stmt).all()]
    out: dict[str, dict] = {}
    for name in metric_names:
        cur_stmt = (
            select(func.avg(MetricPoint.value), func.max(MetricPoint.timestamp))
            .where(and_(
                MetricPoint.service == service,
                MetricPoint.metric_name == name,
                MetricPoint.timestamp >= (now - timedelta(minutes=window_minutes)) if now else True,  # type: ignore[arg-type]
            ))
        )
        avg_cur, _ = db.execute(cur_stmt).one()
        prev_stmt = (
            select(func.avg(MetricPoint.value))
            .where(and_(
                MetricPoint.service == service,
                MetricPoint.metric_name == name,
                MetricPoint.timestamp >= (now - timedelta(minutes=2 * window_minutes)) if now else True,  # type: ignore[arg-type]
                MetricPoint.timestamp < (now - timedelta(minutes=window_minutes)) if now else True,  # type: ignore[arg-type]
            ))
        )
        avg_prev = db.execute(prev_stmt).scalar()
        out[name] = {
            "current": round(avg_cur, 3) if avg_cur is not None else None,
            "previous": round(avg_prev, 3) if avg_prev is not None else None,
            "change_pct": round((avg_cur - avg_prev) / avg_prev * 100, 2)
            if avg_cur is not None and avg_prev not in (None, 0)
            else None,
        }
    return out
