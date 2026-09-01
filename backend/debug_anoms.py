from app.evaluation import _isolated_session, _seed_incident_environment
from app.synthetic.scenarios import EVALUATION_SCENARIOS
from app.ai.tools import ToolRegistry
from sqlalchemy import select

from app.models import MetricPoint

db = _isolated_session()
from app.topology_engine import seed_default_topology

seed_default_topology(db)
scenario = EVALUATION_SCENARIOS[0]
inc = _seed_incident_environment(db, scenario, seed=1000, incident_id_hint="INC-EVAL01")
tools = ToolRegistry(db)
tools.set_incident(inc)
for svc in ["orders-db", "payments-service", "orders-service", "api-gateway"]:
    pairs = db.execute(select(MetricPoint.metric_name).where(MetricPoint.service == svc).distinct()).scalars().all()
    for metric in pairs:
        r = tools.compare_metrics(service=svc, metric=metric)
        if isinstance(r, dict) and r.get("anomaly"):
            z = r["anomaly"]["z_score"]
            expl = r["anomaly"]["explanation"][:70]
            print(f"ANOMALY {svc}/{metric}: z={z} | {expl}")
