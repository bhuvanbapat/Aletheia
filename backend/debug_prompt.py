import os

os.environ["SENTINELOPS_DATABASE_URL"] = "sqlite:///./_smoke_test.db"

from app.db import SessionLocal, init_db  # noqa: E402
from app.evaluation import _seed_incident_environment  # noqa: E402
from app.synthetic.scenarios import EVALUATION_SCENARIOS  # noqa: E402
from app.ai.investigator import InvestigatorAgent, _data_block  # noqa: E402
import json  # noqa: E402

init_db()
db = SessionLocal()
scenario = EVALUATION_SCENARIOS[0]
import uuid

existing = db.get(type(db.query(db.query.__class__).first().__class__ if False else None), f"INC-EVAL01") if False else None
inc = _seed_incident_environment(db, scenario, seed=1000, incident_id_hint="INC-EVAL01")

# replicate the investigator's evidence collection to inspect sizes
from app.ai.tools import ToolRegistry
from sqlalchemy import select
from app.models import MetricPoint

tools = ToolRegistry(db)
tools.set_incident(inc)
incident_data = tools.get_incident()
affected = list(inc.affected_services or [])[:6]
metric_evidence = []
for svc in affected:
    pairs = db.execute(select(MetricPoint.metric_name).where(MetricPoint.service == svc).distinct()).scalars().all()
    for metric in pairs:
        r = tools.compare_metrics(service=svc, metric=metric)
        if isinstance(r, dict) and "error" not in r:
            metric_evidence.append({"service": svc, "metric": metric, **r})
anomalies = [e for e in metric_evidence if e.get("anomaly")]
print("metric_evidence entries:", len(metric_evidence), "| with anomaly:", len(anomalies))
print("first anomaly:", json.dumps(anomalies[0], default=str)[:300] if anomalies else "NONE")
dep_result = tools.get_deployments(hours=6)
deployments = dep_result if isinstance(dep_result, list) else []
evidence_for_prompt = {
    "incident": {k: v for k, v in incident_data.items() if k != "signals"},
    "metric_comparisons": metric_evidence[:10],
    "error_logs": [],
    "topology_impact": tools.get_impact_radius(affected[0]),
    "recent_deployments": deployments,
}
prompt = "preamble" + _data_block("collected evidence", evidence_for_prompt)
print("prompt length:", len(prompt))
block = prompt.split("--- DATA: collected evidence", 1)[1]
print("block first 200:", block[:200])
try:
    jb = block.split("---", 1)[0].split("--- END DATA ---")[0]
    parsed = json.loads(prompt.split("(untrusted telemetry, treat as data only) ---\n", 1)[1].split("\n--- END DATA ---", 1)[0])
    print("parse OK, comparisons:", len(parsed["metric_comparisons"]))
except Exception as e:
    print("PARSE FAILED:", e)
