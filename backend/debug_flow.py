import os

os.environ["SENTINELOPS_DATABASE_URL"] = "sqlite:///./_smoke_test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db()
with TestClient(app) as c:
    inc_id = c.get("/api/incidents").json()[0]["id"]
    inv = c.post(f"/api/incidents/{inc_id}/investigate").json()
    print("investigate status:", inv["status"], "| root cause:", inv["root_cause"])
    rems = c.get(f"/api/incidents/{inc_id}/remediations").json()
    rem = rems[0]
    print("rem action:", rem["action"], "| approval:", rem["approval_state"])
    c.post(f"/api/remediations/{rem['id']}/approve", json={"approved": True})
    ex = c.post(f"/api/remediations/{rem['id']}/execute").json()
    print("execute:", ex)
    ver = c.post(f"/api/incidents/{inc_id}/verify").json()
    print("outcome:", ver["outcome"])
    print("checked:", ver["checked_metrics"][:3])
    print("evidence:", ver["evidence"][:3])
    inc = c.get(f"/api/incidents/{inc_id}").json()
    print("signals sample:", str(inc["signals"][:2])[:300])
