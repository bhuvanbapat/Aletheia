"""Topology engine: DB-backed service graph + impact propagation."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Dependency, Service
from app.synthetic.topology import TopologyGraph, build_default_topology


def load_topology(db: Session) -> TopologyGraph:
    graph = TopologyGraph()
    services = db.execute(select(Service)).scalars().all()
    deps = db.execute(select(Dependency)).scalars().all()
    if not services:
        return build_default_topology()
    for svc in services:
        graph.nodes[svc.name] = {
            "name": svc.name,
            "kind": svc.kind,
            "description": svc.description,
            "environment": svc.environment,
        }
    graph.edges = [(d.source, d.target, d.dep_type, d.critical) for d in deps]
    return graph


def seed_default_topology(db: Session) -> None:
    """Persist the synthetic environment topology into the DB (idempotent)."""
    from app.models import Environment

    if db.execute(select(Service)).scalars().first() is None:
        from app.synthetic.topology import SYNTHETIC_DEPENDENCIES, SYNTHETIC_SERVICES

        if db.execute(select(Environment).where(Environment.name == "production")).scalars().first() is None:
            db.add(Environment(id="env-production", name="production"))
        for svc in SYNTHETIC_SERVICES:
            db.add(Service(id=f"svc-{svc['name']}", name=svc["name"], kind=svc["kind"], description=svc["description"]))
        for source, target, dep_type, critical in SYNTHETIC_DEPENDENCIES:
            db.add(Dependency(source=source, target=target, dep_type=dep_type, critical=critical))
        db.commit()


def topology_dict(graph: TopologyGraph) -> dict:
    return {
        "nodes": [
            {"id": name, "name": name, **{"kind": info.get("kind", "service"), "description": info.get("description", "")}}
            for name, info in graph.nodes.items()
        ],
        "edges": [
            {"source": s, "target": t, "type": dt, "critical": crit}
            for (s, t, dt, crit) in graph.edges
        ],
    }
