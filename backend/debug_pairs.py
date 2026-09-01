from app.evaluation import _isolated_session, _seed_incident_environment
from app.synthetic.scenarios import EVALUATION_SCENARIOS
from app.ai.tools import ToolRegistry
from sqlalchemy import select

from app.models import MetricPoint

db = _isolated_session()
from app.topology_engine import seed_default_topology

seed_default_topology(db)
inc = _seed_incident_environment(db, EVALUATION_SCENARIOS[0], seed=1000, incident_id_hint="INC-EVAL01")
tools = ToolRegistry(db)
tools.set_incident(inc)
for svc in ["orders-db", "payments-service", "orders-service", "api-gateway"]:
    pairs = db.execute(select(MetricPoint.metric_name).where(MetricPoint.service == svc).distinct()).scalars().all()
    print(f"{svc}: {sorted(pairs)}")
    for metric in sorted(pairs):
        r = tools.compare_metrics(service=svc, metric=metric)
        status = "ERROR: " + str(r.get("error")) if isinstance(r, dict) and "error" in r else "ok"
        print(f"   {metric}: {status}")
