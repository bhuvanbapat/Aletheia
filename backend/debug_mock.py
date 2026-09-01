from app.ai.provider import MockProvider
from app.ai.investigator import _data_block

evidence = {
    "incident": {"id": "INC-1", "affected_services": ["orders-db", "payments-service"]},
    "metric_comparisons": [{"service": "orders-db", "metric": "db_connections",
                            "anomaly": {"z_score": 5, "explanation": "db_connections increased"}}],
    "error_logs": [{"message": "Connection pool exhausted"}],
    "topology_impact": {},
    "recent_deployments": [{"service": "payments-service", "version": "v2.4.1"}],
}
prompt = (
    "Return ONLY a JSON object: "
    '{"hypotheses": [{"statement": str, "confidence": float, "evidence_for": [str]}], "reasoning": str}\n'
    + _data_block("collected evidence", evidence)
)
p = MockProvider()
resp = p.complete("sys", prompt)
print(resp.text[:600])
