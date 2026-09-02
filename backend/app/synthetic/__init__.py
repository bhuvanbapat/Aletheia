"""Synthetic production environment: services, topology, and scenario definitions.

All telemetry produced from these modules is synthetic and explicitly labeled
as such (raw_source="synthetic"). The environment models a mid-size e-commerce
system with realistic dependency structure.
"""
from app.synthetic.topology import SYNTHETIC_DEPENDENCIES, SYNTHETIC_SERVICES, build_default_topology

__all__ = ["SYNTHETIC_SERVICES", "SYNTHETIC_DEPENDENCIES", "build_default_topology"]
