"""Smoke test: full backend import + flagship incident flow end-to-end."""
from __future__ import annotations

import os

os.environ["SENTINELOPS_DATABASE_URL"] = "sqlite:///./_smoke_test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db()
client = TestClient(app)


def _enter():
    cm = TestClient(app)
    cm.__enter__()
    return cm


def test_health():
    with TestClient(app) as c:
        resp = c.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["synthetic"] is True


def test_bootstrap_and_incident_flow():
    with TestClient(app) as c:
        # overview reflects seeded environment
        resp = c.get("/api/overview")
        assert resp.status_code == 200
        ov = resp.json()
        assert ov["service_count"] >= 8
        assert ov["active_incident_count"] >= 1

        # incident exists (flagship demo)
        resp = c.get("/api/incidents")
        incidents = resp.json()
        assert len(incidents) >= 1
        inc = incidents[0]
        inc_id = inc["id"]

        # investigate
        resp = c.post(f"/api/incidents/{inc_id}/investigate")
        assert resp.status_code == 200
        inv = resp.json()
        assert inv["status"] == "completed"
        assert len(inv["hypotheses"]) >= 1
        assert inv["root_cause"] is not None

        # agent trace recorded
        resp = c.get(f"/api/agent/runs/{inv['run_id']}/trace")
        trace = resp.json()
        assert len(trace) >= 5

        # remediation proposal exists
        resp = c.get(f"/api/incidents/{inc_id}/remediations")
        rems = resp.json()
        assert len(rems) >= 1
        rem = rems[0]

        # approval required before execution
        resp = c.post(f"/api/remediations/{rem['id']}/execute")
        assert resp.json()["executed"] is False  # blocked - not approved

        # approve then execute
        c.post(f"/api/remediations/{rem['id']}/approve", json={"approved": True, "approver": "test-operator"})
        resp = c.post(f"/api/remediations/{rem['id']}/execute")
        assert resp.json()["executed"] is True

        # verify recovery
        resp = c.post(f"/api/incidents/{inc_id}/verify")
        ver = resp.json()
        assert ver["outcome"] in ("recovered", "partial", "not_recovered", "unknown")
        assert len(ver["evidence"]) >= 1

        # postmortem
        resp = c.post(f"/api/incidents/{inc_id}/postmortem")
        pm = resp.json()
        assert "Root Cause" in pm["content_markdown"]
        assert "## Summary" in pm["content_markdown"]


def test_evaluation_runs():
    with TestClient(app) as c:
        resp = c.post("/api/evaluations/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["aggregate"]["n_scenarios"] == 5
        print("\nEVALUATION:", data["aggregate"])
