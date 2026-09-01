from app.evaluation import _isolated_session, _seed_incident_environment
from app.synthetic.scenarios import EVALUATION_SCENARIOS
from app.ai.investigator import InvestigatorAgent

db = _isolated_session()
from app.topology_engine import seed_default_topology

seed_default_topology(db)
inc = _seed_incident_environment(db, EVALUATION_SCENARIOS[0], seed=1000, incident_id_hint="INC-EVAL01")
agent = InvestigatorAgent(db)
result = agent.investigate(inc)
print("=== trace with errors ===")
for tc in result.tool_calls:
    if tc["status"] == "error":
        print("ERR:", tc["tool"], tc["args"])
