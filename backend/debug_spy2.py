from app.evaluation import _isolated_session, _seed_incident_environment
from app.synthetic.scenarios import EVALUATION_SCENARIOS
from app.ai.investigator import InvestigatorAgent
from app.ai.provider import MockProvider

db = _isolated_session()
from app.topology_engine import seed_default_topology

seed_default_topology(db)
inc = _seed_incident_environment(db, EVALUATION_SCENARIOS[0], seed=1000, incident_id_hint="INC-EVAL01")

calls = []


class SpyProvider:
    name = "spy"
    model = "spy"

    def complete(self, system, user):
        resp = MockProvider().complete(system, user)
        calls.append(resp.text)
        return resp


agent = InvestigatorAgent(db, provider=SpyProvider())
result = agent.investigate(inc)
print("num llm calls:", len(calls))
print("=== CALL 1 (hypotheses) first 500 chars ===")
print(calls[0][:500] if calls else "NONE")
