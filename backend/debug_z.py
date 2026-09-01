import os

os.environ["SENTINELOPS_DATABASE_URL"] = "sqlite:///./_smoke_test.db"

from app.db import SessionLocal, init_db  # noqa: E402
from app.evaluation import _seed_incident_environment  # noqa: E402
from app.synthetic.scenarios import EVALUATION_SCENARIOS  # noqa: E402
from app.metrics_engine import query_series, compute_baseline  # noqa: E402
from datetime import timedelta  # noqa: E402
import statistics  # noqa: E402

init_db()
db = SessionLocal()
inc = _seed_incident_environment(db, EVALUATION_SCENARIOS[0], seed=1000, incident_id_hint="INC-EVAL01")

series = query_series(db, "orders-db", "db_connections")
end = series[-1]["timestamp"]
current_start = end - timedelta(minutes=5)
baseline_start = end - timedelta(minutes=65)
baseline_points = [p for p in series if baseline_start <= p["timestamp"] < current_start]
current_points = [p for p in series if p["timestamp"] >= current_start]
b = compute_baseline(baseline_points)
cur = [p["value"] for p in current_points]
print("baseline n:", b["n"], "mean:", round(b["mean"], 1), "stddev:", round(b["stddev"], 2))
print("current mean:", round(sum(cur) / len(cur), 1))
z = (sum(cur) / len(cur) - b["mean"]) / b["stddev"]
print("z:", round(z, 2))
med = statistics.median([p["value"] for p in baseline_points])
mad = statistics.median([abs(p["value"] - med) for p in baseline_points])
print("median:", med, "mad:", mad, "robust z:", round((sum(cur) / len(cur) - med) / (mad * 1.4826), 2))
