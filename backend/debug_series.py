import os

os.environ["SENTINELOPS_DATABASE_URL"] = "sqlite:///./_smoke_test.db"

from app.db import SessionLocal, init_db  # noqa: E402
from app.evaluation import _seed_incident_environment  # noqa: E402
from app.synthetic.scenarios import EVALUATION_SCENARIOS  # noqa: E402
from app.metrics_engine import query_series, detect_anomalies  # noqa: E402

init_db()
db = SessionLocal()
scenario = EVALUATION_SCENARIOS[0]
inc = _seed_incident_environment(db, scenario, seed=1000, incident_id_hint="INC-EVAL01")

series = query_series(db, "orders-db", "db_connections")
print("points:", len(series))
if series:
    print("first:", series[0]["timestamp"], series[0]["value"])
    print("last:", series[-1]["timestamp"], series[-1]["value"])
    vals = [p["value"] for p in series]
    print("min/max:", min(vals), max(vals))
anoms = detect_anomalies(series, "orders-db", "db_connections")
print("anomalies:", anoms)

# what does compare_metrics do?
from app.ai.tools import ToolRegistry  # noqa: E402

tools = ToolRegistry(db)
r = tools.compare_metrics(service="orders-db", metric="db_connections")
print("compare:", r)
