"""Synthetic service topology for the demo e-commerce environment.

Topology (causal direction: upstream calls downstream):

    api-gateway ──▶ auth-service ──▶ auth-db
    api-gateway ──▶ orders-service ─▶ payments-service ─▶ orders-db
    orders-service ─▶ inventory-service ─▶ inventory-db
    orders-service ─▶ notification-service ─▶ external-email-provider
"""
from __future__ import annotations

from dataclasses import dataclass, field

SYNTHETIC_SERVICES: list[dict] = [
    {"name": "api-gateway", "kind": "service", "description": "Public entry point; routes and rate-limits all client traffic"},
    {"name": "auth-service", "kind": "service", "description": "Handles authentication and session validation"},
    {"name": "orders-service", "kind": "service", "description": "Order placement, orchestration of payments/inventory/notifications"},
    {"name": "payments-service", "kind": "service", "description": "Charges payment methods; writes to orders-db"},
    {"name": "inventory-service", "kind": "service", "description": "Reserves and releases stock"},
    {"name": "notification-service", "kind": "service", "description": "Sends order confirmations via email provider"},
    {"name": "orders-db", "kind": "database", "description": "Primary OLTP database for orders and payments"},
    {"name": "inventory-db", "kind": "database", "description": "Inventory state store"},
    {"name": "auth-db", "kind": "database", "description": "Credentials and session store"},
    {"name": "external-email-provider", "kind": "external", "description": "Third-party email delivery"},
]

# (source, target, dep_type, critical)
SYNTHETIC_DEPENDENCIES: list[tuple[str, str, str, bool]] = [
    ("api-gateway", "auth-service", "depends_on", True),
    ("api-gateway", "orders-service", "depends_on", True),
    ("auth-service", "auth-db", "uses", True),
    ("orders-service", "payments-service", "depends_on", True),
    ("orders-service", "inventory-service", "depends_on", True),
    ("orders-service", "notification-service", "depends_on", False),
    ("payments-service", "orders-db", "uses", True),
    ("orders-service", "orders-db", "uses", True),
    ("inventory-service", "inventory-db", "uses", True),
    ("notification-service", "external-email-provider", "depends_on", False),
]


@dataclass
class TopologyGraph:
    """In-memory directed graph over service names."""

    nodes: dict[str, dict] = field(default_factory=dict)
    edges: list[tuple[str, str, str, bool]] = field(default_factory=list)

    def downstream(self, service: str) -> list[str]:
        """Services `service` depends on (its dependencies)."""
        return [t for (s, t, _, _) in self.edges if s == service]

    def upstream(self, service: str) -> list[str]:
        """Services that depend on `service` (its dependents)."""
        return [s for (s, t, _, _) in self.edges if t == service]

    def descendants(self, service: str) -> list[str]:
        """Transitive dependencies of `service`."""
        seen: set[str] = set()
        stack = [service]
        while stack:
            current = stack.pop()
            for dep in self.downstream(current):
                if dep not in seen:
                    seen.add(dep)
                    stack.append(dep)
        return sorted(seen)

    def impact_radius(self, service: str) -> list[str]:
        """Services affected if `service` degrades (transitive dependents + itself)."""
        seen: set[str] = {service}
        stack = [service]
        while stack:
            current = stack.pop()
            for dep in self.upstream(current):
                if dep not in seen:
                    seen.add(dep)
                    stack.append(dep)
        return sorted(seen)

    def propagation_path(self, root: str) -> list[dict]:
        """Causal propagation: root → direct impact → downstream impact → user impact."""
        direct = self.upstream(root)
        impacted: dict[str, int] = {}
        for svc in direct:
            for up in self.impact_radius(svc):
                if up != root and up not in direct:
                    impacted[up] = max(impacted.get(up, 0), self._hop_distance(root, up))
        return [
            {"stage": "root", "services": [root]},
            {"stage": "direct_impact", "services": sorted(direct)},
            {"stage": "downstream_impact", "services": sorted(impacted.keys())},
            {
                "stage": "user_impact",
                "services": ["api-gateway"] if "api-gateway" in impacted else sorted(set(impacted) | set(direct)),
            },
        ]

    def _hop_distance(self, root: str, target: str) -> int:
        # BFS distance from root upstream (towards dependents)
        from collections import deque

        queue: deque[tuple[str, int]] = deque([(root, 0)])
        visited = {root}
        while queue:
            node, dist = queue.popleft()
            if node == target:
                return dist
            for up in self.upstream(node):
                if up not in visited:
                    visited.add(up)
                    queue.append((up, dist + 1))
        return 0


def build_default_topology() -> TopologyGraph:
    graph = TopologyGraph()
    for svc in SYNTHETIC_SERVICES:
        graph.nodes[svc["name"]] = svc
    graph.edges = list(SYNTHETIC_DEPENDENCIES)
    return graph
