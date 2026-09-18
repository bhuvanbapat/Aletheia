# Aletheia — AI SRE & Incident Intelligence Platform

Aletheia ingests telemetry, correlates signals across a service dependency
graph, detects incidents with a deterministic rule engine, and then runs a
controlled **AI investigation** that must gather evidence before naming a root
cause. Every conclusion is evidence-backed. Every remediation requires human
approval. Recovery is **measured against post-remediation telemetry**, never
claimed.

> **Everything in the demo runs against a synthetic production environment**
> (a simulated e-commerce system of 10 services). No real infrastructure is
> touched, no API key is required, and all results are deterministic in mock
> mode. The UI labels this clearly (`SYNTHETIC DEMO`).

## What it demonstrates

| Capability | Implementation |
|---|---|
| Telemetry ingestion | JSON events, normalization, dedup, malformed-entry resilience |
| Metrics engine | Baselines, rolling windows, interpretable anomaly detection (robust modified z-score) |
| Service topology | Dependency graph, impact propagation, root → downstream → user paths |
| Incident correlation | Deterministic rule engine (DB exhaustion, deployment regression, resource saturation, cache failure, dependency timeout) — one incident, not an alert storm |
| AI investigation | Evidence collection via typed tools → hypothesis generation → ranking → RCA. Provider abstraction: OpenAI-compatible endpoint or deterministic mock |
| Evidence-first RCA | Every hypothesis stores its supporting evidence; the UI exposes it |
| Controlled remediation | Whitelisted simulation-only actions; approval REQUIRED by default; every action is recorded (who/when/why/params/result) |
| Recovery verification | Post-remediation metrics compared against pre-incident baseline → `recovered / partial / not_recovered / unknown` with gap-closure percentages |
| Postmortems | Structured, generated from stored incident data only |
| Agent observability | Every tool call traced: name, args, duration, status, result |
| Security | Prompt-injection quarantine, secret redaction, action whitelist, no host command execution |
| Evaluation harness | 5 benchmark scenarios with known ground truth, scored end-to-end |

## Quick start (no API key needed)

```bash
# Backend
cd backend
pip install fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings httpx pytest
python -m uvicorn app.main:app --port 8010

# Frontend (new terminal)
cd frontend
npm install
npm run dev
# open the printed URL (e.g. http://localhost:5174)
```

The backend bootstraps the synthetic environment and one flagship incident
(database connection-pool exhaustion after a deployment) on startup.

**Demo path:** Overview → Incidents → open the incident → **Run investigation**
→ review hypotheses/evidence/agent trace → **Approve** the proposed
remediation → **Execute (simulated)** → **Verify recovery** → **Generate
postmortem** → Evaluations → **Run benchmark suite**.

## Docker

```bash
docker build -t Aletheia-backend ./backend
docker run -p 8000:8000 Aletheia-backend
# API at http://localhost:8000 — OpenAPI docs at /docs
```

## Enabling a real LLM (optional)

```bash
export Aletheia_LLM_BASE_URL=https://api.openai.com/v1   # or any OpenAI-compatible endpoint
export Aletheia_LLM_API_KEY=...
export Aletheia_LLM_MODEL=gpt-4o-mini
```

Without a key the platform runs in deterministic **mock mode** — the full
pipeline still works end-to-end and is clearly labeled `DEMO MODE` in the UI.

## Repository layout

```
backend/
  app/
    synthetic/        synthetic environment: topology, scenarios, telemetry generator
    ingestion.py      event parsing / normalization / dedup / resilience
    metrics_engine.py baselines + interpretable anomaly detection
    log_engine.py     structured log queries
    topology_engine.py service graph + impact propagation
    incident_rules.py deterministic correlation rule engine
    incidents.py      incident lifecycle + timelines
    ai/
      provider.py     LLMProvider abstraction (OpenAI-compatible | deterministic mock)
      tools.py        the investigator's typed tool registry
      investigator.py the agent loop (evidence → hypotheses → RCA → recommendation)
    remediation.py    controlled remediation (whitelist + approval gate)
    verification.py   recovery measurement
    postmortem.py     report generation from stored data
    evaluation.py     benchmark harness (isolated scenario DBs)
    security.py       secret redaction + prompt-injection quarantine
    main.py           FastAPI app
  tests/              unit + e2e + live QA suite
frontend/             React + TypeScript + Vite dashboard
docs/                 architecture, security, evaluation, demo, ADRs, resume notes
```

## Tests

```bash
cd backend
python -m pytest tests/ -v          # 28 tests: units, e2e lifecycle, benchmark
python tests/live_qa.py             # 9 live checks against a running server
```

## Honest limitations

- All telemetry is synthetic (clearly labeled). Benchmark results measure
  the pipeline against clean simulated signals, **not** real-world RCA
  performance — real incidents are noisier.
- The mock LLM is deterministic evidence-based logic, not a language model.
- Single-process deployment (SQLite); designed to port to PostgreSQL.
- Remediation acts only on the simulation; there is no real infrastructure
  connector (by design).

See `docs/` for the full architecture, threat model, evaluation methodology,
ADRs, and an interview prep guide.

