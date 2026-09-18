# Aletheia — Resume Notes

## Project description (concise)

> Aletheia — AI-assisted SRE platform: ingests telemetry, correlates
> signals across a service dependency graph, detects incidents with a
> deterministic rule engine, then runs a controlled AI investigation that
> must gather evidence before naming root causes. Evidence-backed RCA,
> approval-gated simulated remediation, measured recovery verification,
> postmortem generation, and a 5-scenario benchmark harness. Runs fully
> offline in deterministic mock mode.

## Actual stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · SQLite (Postgres-ready)
· React 18 · TypeScript · Vite · Recharts · Docker · GitHub Actions · pytest

## Strongest technical features (all real, verifiable in repo)

1. **Hybrid rule+AI architecture** — deterministic engine creates incidents;
   the agent only investigates them. LLM never invents baselines or
   incidents. (ADR-004)
2. **Evidence-first RCA** — hypotheses carry their evidence; postmortems may
   only cite stored records; recovery requires measured telemetry. (ADR-007)
3. **Robust anomaly detection** — Iglewicz-Hoaglin modified z-score
   (median/MAD) chosen because plain mean/stddev measurably failed
   (z≈2.5 for a 145% change) when an incident pollutes its own baseline
   window.
4. **Topological reasoning** — impact radius/propagation paths separate
   root causes from downstream symptoms; ranking demotes symptom kinds.
5. **Security engineering** — prompt-injection quarantine, secret redaction
   (JWT/PEM/API keys), whitelisted simulation-only remediation with a
   server-enforced approval gate, no subprocess code path anywhere.
6. **Observability of the observer** — every agent tool call traced
  (duration, status, args, result), token estimates, loop-safety stop
   reasons.
7. **Evaluation harness with isolated scenario DBs** — benchmarks cannot
   cross-contaminate; caught four real bugs during development
   (evidence-loss indentation, z-dilution, prompt-boilerplate action
   matching, symptom-over-cause ranking).

## Actual benchmark metrics (synthetic, seeded, deterministic mock mode)

- Root-cause accuracy: 5/5 scenarios
- Affected-service accuracy: 5/5
- Remediation correctness: 5/5
- Recovery verification: 5/5
- Average scenario score: 1.00

**Caveat to state in interviews:** these measure the deterministic pipeline
against clean synthetic signals — a correctness/sanity bar, not real-world
RCA performance. Saying this unprompted is a strength.

## Resume bullets (candidates)

- Built Aletheia, an AI SRE platform pairing a deterministic correlation
  engine (robust modified z-score anomaly detection, service-topology
  impact propagation) with an evidence-first AI investigator that must
  collect telemetry before ranking root-cause hypotheses; 5/5 root-cause
  accuracy on a synthetic benchmark with known ground truth.
- Engineered the safety spine: whitelisted simulation-only remediation with
  a server-enforced human approval gate, prompt-injection quarantine of
  untrusted telemetry, and secret redaction at ingestion; recovery claims
  require measured post-remediation telemetry, verified by live QA.
- Delivered a modular FastAPI + React/TypeScript platform with full agent
  observability (traced tool calls, durations, token estimates), an
  isolated in-memory evaluation harness, Docker packaging, and CI (pytest +
  ruff + tsc + build + container smoke-test).

## Interview talking points

- Why the median/MAD z-score (the concrete failure story of mean/stddev).
- Why incidents come from rules, not the LLM (hallucination control).
- Why symptom-vs-cause priors exist (every scenario has error-rate spikes;
  the interesting question is which anomaly is a *state* change).
- Why verification owns the `resolved` transition (no fake success).
- Why benchmark DBs are isolated (measurement integrity, found the hard way).

See docs/INTERVIEW_GUIDE.md for the full question set.

