from app.evaluation import _isolated_session, _seed_incident_environment
from app.synthetic.scenarios import EVALUATION_SCENARIOS
from app.ai import investigator as inv_mod
from app.ai.investigator import InvestigatorAgent

db = _isolated_session()
from app.topology_engine import seed_default_topology

seed_default_topology(db)
inc = _seed_incident_environment(db, EVALUATION_SCENARIOS[0], seed=1000, incident_id_hint="INC-EVAL01")

# monkey-patch _parse_hypotheses to see what it gets
orig_parse = InvestigatorAgent._parse_hypotheses
orig_complete_holder = {}


class SpyProvider:
    name = "spy"
    model = "spy"

    def complete(self, system, user):
        from app.ai.provider import MockProvider

        resp = MockProvider().complete(system, user)
        orig_complete_holder["last"] = (system[:50], user[:100], resp.text[:200])
        return resp


agent = InvestigatorAgent(db, provider=SpyProvider())
result = agent.investigate(inc)
print("status:", result.status, "| stop:", result.stop_reason)
print("hypotheses:")
for h in result.hypotheses:
    print(" ", h["confidence"], h["statement"])
sys, usr, resp = orig_complete_holder.get("last", ("", "", ""))
print("MOCK RESP (first 200):", resp)
