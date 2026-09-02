# ADR-001: Modular monolith

**Status:** Accepted

## Context
The platform needs many cooperating subsystems (ingestion, metrics,
topology, correlation, AI, remediation, verification). A microservices
split would add orchestration overhead with no benefit for a
single-machine demo/simulation.

## Decision
Single FastAPI process, strictly modularized by domain
(`ingestion`, `metrics_engine`, `incident_rules`, `ai/*`,
`remediation`, `verification`, ...). Dependencies flow one way:
rules depend on engines; the agent depends on tools; remediation
depends on nothing upstream. (Verified with a code graph: no cycles.)

## Consequences
- Simple to run, test, and reason about; the correlation and agent
  loops share one DB session cheaply.
- Scaling later means extracting modules behind APIs — the module
  seams already exist.
