import os

os.environ["SENTINELOPS_DATABASE_URL"] = "sqlite:///./_smoke_test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db()
with TestClient(app) as c:
    result = c.post("/api/evaluations/run").json()
    for s in result["scenarios"]:
        print(f"{s['scenario_id']}: RC={s['root_cause_correct']} score={s['score']}")
        print(f"  predicted: {s['predicted_root_cause']}")
        print(f"  known:     {s['known_root_cause']}")
