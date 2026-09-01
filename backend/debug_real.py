import os

os.environ["SENTINELOPS_DATABASE_URL"] = "sqlite:///./_smoke_test.db"

from app.db import SessionLocal, init_db  # noqa: E402
from app.evaluation import _seed_incident_environment  # noqa: E402
from app.synthetic.scenarios import EVALUATION_SCENARIOS  # noqa: E402
from app.ai.investigator import InvestigatorAgent, INVESTIGATION_SYSTEM_PROMPT, _data_block  # noqa: E402
from app.ai.provider import MockProvider  # noqa: E402
from app.ai.tools import ToolRegistry  # noqa: E402
from sqlalchemy import select  # noqa: E402
from app.models import MetricPoint  # noqa: E402

init_db()
db = SessionLocal()
scenario = EVALUATION_SCENARIOS[0]
inc = _seed_incident_environment(db, scenario, seed=1000, incident_id_hint="INC-EVAL01")

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
print("anomalies found:", len(anomalies))
for a in anomalies:
    print(" -", a["service"], a["metric"], "z=", a["anomaly"]["z_score"])

dep_result = tools.get_deployments(hours=6)
deployments = dep_result.get("items", []) if isinstance(dep_result, dict) else dep_result
print("deployments:", deployments)

evidence_for_prompt = {
    "incident": {k: v for k, v in incident_data.items() if k != "signals"},
    "metric_comparisons": metric_evidence[:10],
    "error_logs": [],
    "topology_impact": tools.get_impact_radius(affected[0]),
    "recent_deployments": deployments,
}
prompt = (
    "Based on the following structured evidence, generate ranked root-cause hypotheses.\n"
    "Return ONLY a JSON object: "
    '{"hypotheses": [{"statement": str, "confidence": float 0-1, '
    '"evidence_for": [str], "evidence_against": [str]}], "reasoning": str}\n'
    + _data_block("collected evidence", evidence_for_prompt)
)
print("prompt len:", len(prompt))
provider = MockProvider()
resp = provider.complete(INVESTIGATION_SYSTEM_PROMPT, prompt)
print("MOCK OUTPUT:", resp.text[:400])
