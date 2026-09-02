"""Temporary diagnostic: dump engine URL + DB state inside pytest context."""
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal, engine, init_db
from app.main import app
from app.models import Incident, Service, TelemetryEvent

init_db()


def test_diag():
    print("\nENGINE URL:", engine.url)
    with TestClient(app) as c:
        ov = c.get("/api/overview").json()
        print("OVERVIEW active_incident_count:", ov["active_incident_count"])
    db = SessionLocal()
    print("services:", db.execute(select(func.count(Service.id))).scalar())
    print("events:", db.execute(select(func.count(TelemetryEvent.id))).scalar())
    incs = db.execute(select(Incident)).scalars().all()
    print("incidents:", [(i.id, i.status, i.scenario_id) for i in incs])
