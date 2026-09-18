# ADR-003: SQLite / local-first storage

**Status:** Accepted

## Context
The platform must run anywhere (laptop, CI, container) with zero setup,
while the data model (events, metrics, incidents, hypotheses, evidence,
traces) is inherently relational.

## Decision
SQLAlchemy 2.0 ORM over SQLite with an explicit, typed schema
(`app/models.py`). No database-specific features are used; the engine is
configured via `ALETHEIA_DATABASE_URL`, so PostgreSQL is a config
change. Benchmark scenarios use isolated in-memory SQLite instances so
measurements cannot cross-contaminate.

## Consequences
- Zero-config start; tests run in seconds.
- Write concurrency is limited (fine for a single-process monolith);
  porting to Postgres for multi-process deployment is straightforward
  because no SQLite-specific SQL was written.


