# Aletheia — Complete Project Documentation

> **What this document is:** an exhaustive, inch-by-inch record of everything in this repository —
> every component, every file, every mechanism, every decision, every bug found and fixed, and
> every verification result with evidence. Written to be the single source of truth for a
> reviewer, interviewer, or future maintainer.

---

## Table of Contents

1. [The Problem Being Solved](#1-the-problem-being-solved)
2. [What Aletheia Is — Precisely](#2-what-Aletheia-is--precisely)
3. [The Core Idea in One Diagram](#3-the-core-idea-in-one-diagram)
4. [Repository Map — Every File Explained](#4-repository-map--every-file-explained)
   - 4.1 [Backend application (`backend/app/`)](#41-backend-application)
   - 4.2 [Synthetic environment (`backend/app/synthetic/`)](#42-synthetic-environment)
   - 4.3 [AI layer (`backend/app/ai/`)](#43-ai-layer)
   - 4.4 [Backend tests (`backend/tests/`)](#44-backend-tests)
   - 4.5 [Frontend (`frontend/src/`)](#45-frontend)
   - 4.6 [Documentation (`docs/`)](#46-documentation)
   - 4.7 [Root, Docker, and CI files](#47-root-docker-and-ci-files)
5. [Every Mechanism, Explained in Detail](#5-every-mechanism-explained-in-detail)
   - 5.1 [Telemetry ingestion pipeline](#51-telemetry-ingestion-pipeline)
   - 5.2 [Anomaly detection — the math and why](#52-anomaly-detection--the-math-and-why)
   - 5.3 [Service topology and impact propagation](#53-service-topology-and-impact-propagation)
   - 5.4 [The correlation rule engine](#54-the-correlation-rule-engine)
   - 5.5 [Incident lifecycle and the timeline](#55-incident-lifecycle-and-the-timeline)
   - 5.6 [The AI investigator — every step](#56-the-ai-investigator--every-step)
   - 5.7 [Hypothesis ranking — the formula](#57-hypothesis-ranking--the-formula)
   - 5.8 [The mock LLM provider — deterministic reasoning](#58-the-mock-llm-provider--deterministic-reasoning)
   - 5.9 [Controlled remediation — the safety spine](#59-controlled-remediation--the-safety-spine)
   - 5.10 [Recovery verification — measured, never claimed](#510-recovery-verification--measured-never-claimed)
   - 5.11 [Postmortem generation](#511-postmortem-generation)
   - 5.12 [The evaluation harness](#512-the-evaluation-harness)
   - 5.13 [Security mechanisms](#513-security-mechanisms)
   - 5.14 [Agent observability — the platform observing itself](#514-agent-observability--the-platform-observing-itself)
6. [The Five Benchmark Scenarios — Full Specifications](#6-the-five-benchmark-scenarios--full-specifications)
7. [The API Surface — All 34 Endpoints](#7-the-api-surface--all-34-endpoints)
8. [The Frontend — Every Screen](#8-the-frontend--every-screen)
9. [The Database Schema — All 15 Entities](#9-the-database-schema--all-15-entities)
10. [Bugs Found and Fixed During Development](#10-bugs-found-and-fixed-during-development)
11. [Verification Evidence — Everything Ever Measured](#11-verification-evidence--everything-ever-measured)
12. [Known Limitations — Stated Plainly](#12-known-limitations--stated-plainly)
13. [How to Run Everything](#13-how-to-run-everything)

---

## 1. The Problem Being Solved

When a distributed system breaks, an on-call engineer faces:

- **Thousands of signals at once** — error rates spike on many services simultaneously,
  not just the one that's broken.
- **Symptoms masquerading as causes** — the gateway's error rate rises because a database
  pool exhausted two layers downstream. Sorting symptoms from causes is the hard part.
- **Alert storms** — naive monitoring fires one alert per signal, so one real incident
  becomes 40 pages.
- **Confident, evidence-free guesses** — both humans and LLMs are prone to "the database
  is the problem" without proof.
- **Unverifiable remediation** — "I restarted it, should be fixed" — was it? Who approved
  that? What actually recovered?

Existing "AI for SRE" demos mostly pipe logs into an LLM and print a summary. That solves
none of the above. Aletheia is built to demonstrate what a *serious* answer looks like.

## 2. What Aletheia Is — Precisely

Aletheia is an **AI-assisted SRE and incident-intelligence platform** that:

1. **Ingests telemetry** (structured events, metrics, deployments) with normalization,
   deduplication, secret redaction, and malformed-entry resilience.
2. **Detects anomalies** in metrics using interpretable statistics (robust modified
   z-score), with every anomaly carrying a human-readable explanation of *why* it was
   flagged, containing real values — never fabricated baselines.
3. **Maintains a service dependency graph** and uses it to reason about impact: who is
   downstream of whom, what is a root vs. a symptom.
4. **Correlates signals into incidents** using a deterministic rule engine — one incident,
   not an alert storm — with severity, confidence, affected services, and evidence hints.
5. **Runs an AI investigation** whose agent *must collect evidence* via typed tools before
   forming hypotheses; ranks root-cause hypotheses with an explainable formula; recommends
   one remediation — all traced, all observable.
6. **Gates every remediation** behind a whitelist, a mode matrix, and (by default) explicit
   human approval. Actions execute only in simulation.
7. **Measures recovery** from post-remediation telemetry — an incident cannot be marked
   resolved without a measured `recovered` outcome.
8. **Generates postmortems** whose every factual line cites stored data.
9. **Evaluates itself** against 5 benchmark scenarios with known ground truth, in isolated
   databases, scoring root-cause accuracy, affected-service accuracy, remediation
   correctness, and recovery verification.

It runs entirely offline in **deterministic mock mode** (no API key), or against any
**OpenAI-compatible endpoint** via environment configuration.

## 3. The Core Idea in One Diagram

```
                        ┌─────────────────────────────────────────────┐
                        │   SYNTHETIC PRODUCTION ENVIRONMENT          │
                        │   10 services · dependency graph · seeded   │
                        │   telemetry generator (baselines + causal   │
                        │   incident windows + recovery windows)      │
                        └──────────────────────┬──────────────────────┘
                                               │
                        ┌──────────────────────▼──────────────────────┐
   DETERMINISTIC        │   INGESTION                                 │
   CORE (no AI)         │   normalize → redact secrets → quarantine    │
   ────────────────►    │   injections → dedup → store                │
                        └──────────────────────┬──────────────────────┘
                                               │
            ┌──────────────────────────────────┼──────────────────────────┐
            ▼                                  ▼                          ▼
   ┌────────────────┐                ┌──────────────────┐       ┌────────────────┐
   │ METRICS ENGINE │                │   LOG ENGINE     │       │ TOPOLOGY       │
   │ median/MAD     │                │   filter/search  │       │ impact radius  │
   │ modified z     │                │                  │       │ propagation    │
   └───────┬────────┘                └────────┬─────────┘       └───────┬────────┘
           │        anomalies                  │ logs                    │
           └────────────────┬───────────────────┴────────────────────────┘
                            ▼
                ┌───────────────────────────────┐
                │  CORRELATION RULE ENGINE       │  ← one incident,
                │  5 rules + dedup               │    not an alert storm
                └───────────────┬───────────────┘
                                ▼
                ┌───────────────────────────────┐
   AI LAYER     │  INCIDENT (open)               │
   (reasons on  └───────────────┬───────────────┘
   structured  ┌─────────────────▼──────────────────┐
   evidence,   │  AI INVESTIGATOR AGENT              │
   never does  │  12 typed tools, every call traced  │
   arithmetic) │  evidence → hypotheses → rank →     │
               │  recommend                         │
               └─────────────────┬──────────────────┘
                                 ▼
                ┌───────────────────────────────┐
                │  REMEDIATION (proposed)         │
                │  whitelist + mode matrix +      │
                │  ★ HUMAN APPROVAL REQUIRED ★    │
                └───────────────┬────────────────┘
                                ▼  (simulated execution only)
                ┌───────────────────────────────┐
                │  VERIFICATION ENGINE            │
                │  measured gap-closure vs        │
                │  baseline → recovered/partial/  │
                │  not_recovered/unknown          │
                │  (ONLY this resolves incident)  │
                └───────────────┬────────────────┘
                                ▼
                ┌───────────────────────────────┐
                │  POSTMORTEM (from stored data  │
                │  only) + EVALUATION (ground     │
                │  truth scoring)                 │
                └───────────────────────────────┘
```

The single most important design rule: **the deterministic core creates incidents; the AI
only investigates them.** The LLM cannot invent an incident, cannot fabricate a baseline,
cannot execute an action, and cannot claim recovery.

---

## 4. Repository Map — Every File Explained

### 4.1 Backend application

All paths relative to `backend/`.

| File | Lines | What it is, in detail |
|---|---|---|
| `app/config.py` | 29 | Pydantic-settings configuration. Every knob is env-driven (`ALETHEIA_*` prefix): DB URL, LLM base URL/key/model/timeout, agent loop limits (max tool calls 40, max repeated calls 3, runtime 120s), remediation mode (default `approval_required`), synthetic seed. `llm_enabled` is a property: true only when base URL, key, and non-"mock" model are ALL set. `@lru_cache` so it's a singleton. |
| `app/db.py` | 20 | SQLAlchemy 2.0 engine + session factory. `check_same_thread=False` for SQLite; `get_db()` yields a session for FastAPI DI; `init_db()` creates all tables. PostgreSQL is a config change — no SQLite-specific SQL anywhere. |
| `app/models.py` | 190 | **All 15 entities** (see §9): Environment, Service, Dependency, TelemetryEvent, MetricPoint, Deployment, Incident, Hypothesis, Evidence, AgentRun, ToolCall, Remediation, Verification, Postmortem, EvaluationCase, IngestionStats. Helpers: `utcnow()` (timezone-aware) and `new_id(prefix)` (`"INC-" + 12 hex chars`). |
| `app/schemas.py` | 46 | Pydantic request/response models: `TelemetryEventIn` (documents the well-formed event shape), `IngestResponse` (received/accepted/duplicates/malformed/parse_errors), `ApprovalRequest` (approver + approved flag), `SettingsOut` (provider, mode, demo flag, limits), `InvestigationOut`. |
| `app/security.py` | 84 | Secret redaction + prompt-injection defense. `_SECRET_PATTERNS`: 5 regex families for secret-looking keys (api_key, password, token, private_key, credential). `_SECRET_VALUE_RE`: literal secret values (OpenAI `sk-…`, GitHub `ghp_…`, AWS `AKIA…`, JWTs). `_PEM_BLOCK_RE`: entire PEM private-key blocks. `redact_mapping()` recurses nested dicts replacing matching keys AND values with `[REDACTED]`, returning the kinds it redacted. `contains_injection_markers()`: heuristic detection of 6 injection phrasings. `quarantine_explanation()`: the standard explanation attached to flagged telemetry. |
| `app/ingestion.py` | 167 | The resilient ingestion pipeline (detailed in §5.1). `normalize_event()` (timestamp parsing for ISO/epoch/None, severity normalization, metadata defense, dedup-hash computation), `ingest_events()` (batch stats, never crashes, counts malformed with capped error samples), `ingest_metric_points()`. |
| `app/metrics_engine.py` | 150 | `query_series()` (time-filtered raw points), `compute_baseline()` (mean/stddev/min/max/n), `detect_anomalies()` (the robust modified z-score — full math and rationale in §5.2), `ewma()`, `summarize_service_metrics()` (current-window vs previous-window per metric for service views). |
| `app/log_engine.py` | 91 | Structured log queries: filter by service/severity/event_type/time window/free-text search (ILIKE)/trace_id, with limit+offset and a matching `count_logs()`. `log_stats()` for severity counts over the recent window (Overview page). `event_to_dict()` serializer. |
| `app/topology_engine.py` | 44 | Loads the DB-persisted graph into the in-memory `TopologyGraph` (from `synthetic/topology.py`); `seed_default_topology()` persists the synthetic environment idempotently; `topology_dict()` for API serialization. |
| `app/incident_rules.py` | 301 | **The deterministic correlation engine** (detailed in §5.4): `CorrelationContext` (shared read-only view: anomalies cache, error logs, deployments, topology), `CorrelationRule` base, and 5 rules — DatabaseExhaustionRule, DeploymentRegressionRule, ResourceSaturationRule, CacheFailureRule, DependencyTimeoutRule — plus `run_correlation()` which evaluates all rules, swallows per-rule exceptions, sorts by confidence. |
| `app/incidents.py` | 158 | Incident lifecycle: `detect_incidents()` runs correlation and creates incidents with **dedup** (skips if an open incident shares category + overlapping affected services), persists evidence hints; `_title_for()` human labels per category; `incident_to_dict()`; `build_timeline()` — merges deployment events (from signals AND the deployments table within 30min pre-incident), ERROR/CRITICAL logs for affected services, the detection event, remediation proposals/executions, and verification outcomes, all chronologically sorted. |
| `app/remediation.py` | 147 | The safety spine (detailed in §5.9): `ALLOWED_ACTIONS` whitelist (6 verbs), `ACTION_EFFECTS` (per-verb modeled effects), `propose_remediation()` (validates whitelist, records initiator/reason/expected effect/risk), `approve_remediation()` / `reject_remediation()` (explicit recorded states with approver identity), `execute_remediation()` (enforces the mode matrix and approval gate, generates recovery telemetry in the simulation, records result, transitions incident → mitigated). |
| `app/verification.py` | 119 | Recovery measurement (detailed in §5.10): `verify_recovery()` compares post-remediation metric means against pre-incident baseline and peak, computes gap-closure per metric, derives the outcome (`recovered`/`partial`/`not_recovered`/`unknown`), writes per-metric evidence strings with real numbers, and is the ONLY code that sets `incident.status = resolved`. |
| `app/postmortem.py` | 172 | Report generator (detailed in §5.11): reads incident, evidence, hypotheses, remediations, verifications; emits 13 markdown sections; every factual line cites stored records. |
| `app/evaluation.py` | 232 | Benchmark harness (detailed in §5.12): `_seed_incident_environment()` (50min baseline + 15min incident window + deployment row), `_isolated_session()` (fresh in-memory SQLite per scenario), `_concept_match()` (ground-truth scoring), `score_case()`, `run_evaluation()` (full pipeline per scenario: investigate → propose → approve → execute → verify → score). |
| `app/bootstrap.py` | 70 | Idempotent startup seeding: persists topology, generates the flagship DB-exhaustion incident telemetry, records the deployment, creates the incident bound to scenario ground truth. Skips if the incident already exists. |
| `app/main.py` | 418 | The FastAPI app: lifespan-managed bootstrap, CORS (localhost dev origins), and **all 34 endpoints** (see §7) with typed request/response models and OpenAPI docs. Notable internals: permissive raw-body telemetry ingestion (malformed counted, never 422), the overview aggregation (computes error/latency/anomaly counts from stored data — nothing hard-coded), and 404s on unknown IDs (fixed after adversarial testing found one violation). |

### 4.2 Synthetic environment

| File | Lines | What it is |
|---|---|---|
| `app/synthetic/topology.py` | 104 | The world definition: `SYNTHETIC_SERVICES` (10 nodes: api-gateway, auth-service, orders-service, payments-service, inventory-service, notification-service, orders-db, inventory-db, auth-db, external-email-provider — each typed service/database/external with a description) and `SYNTHETIC_DEPENDENCIES` (10 directed edges with `depends_on`/`uses` types and criticality flags). `TopologyGraph` implements the graph algorithms: `downstream()`, `upstream()`, `descendants()` (transitive deps), `impact_radius()` (transitive dependents — who suffers if X degrades), `propagation_path()` (root → direct_impact → downstream_impact → user_impact stages), `_hop_distance()` (BFS). |
| `app/synthetic/scenarios.py` | 274 | **The incident scenario library.** Dataclasses: `MetricProfile` (service, metric, baseline, peak, ramp_minutes, recovery_minutes), `LogSignal` (severity, service, event_type, message, offset_minutes, metadata), `Scenario` (id, title, category, trigger, root_service, severity, **known_root_cause**, **root_cause_concepts** [ground-truth scoring keys], expected_affected_services, expected_evidence, acceptable_remediations, metrics, logs, deployment, recovery behavior). Five fully-specified scenarios (see §6). `EVALUATION_SCENARIOS` is the benchmark set. |
| `app/synthetic/generator.py` | 215 | Seeded, deterministic telemetry generation. `METRIC_BASELINES`: per-service healthy values for 20+ metrics. `generate_baseline_window()`: healthy telemetry with ±4% noise. `generate_incident_window()`: drives each scenario metric along a logistic S-curve from baseline to peak over `ramp_minutes`, then plateaus (incident unmitigated); emits the scenario's causal log sequence with trace IDs; keeps healthy services running background telemetry; records the deployment if scenario-driven. `generate_post_remediation_window()`: decays each scenario metric from peak back toward baseline over `recovery_minutes` — this is what verification measures. `_dedup_hash()`: content-hash for idempotent ingestion. |
| `app/synthetic/__init__.py` | 7 | Re-exports the topology API. |

### 4.3 AI layer

| File | Lines | What it is |
|---|---|---|
| `app/ai/provider.py` | 249 | **Provider abstraction.** `LLMResponse` dataclass (text, token counts, cost, provider, model). `LLMProvider` Protocol. `MockProvider`: deterministic zero-cost reasoning — parses the structured evidence JSON from the prompt's DATA block and derives hypotheses with the explainable ranking formula (§5.7), derives the remediation from the top-hypothesis DATA block (never from prompt boilerplate), full detail in §5.8. `OpenAICompatibleProvider`: lazy-imported httpx, `/chat/completions`, temperature 0.1, usage-based token counts — works with OpenAI, vLLM, Ollama, LM Studio. `build_provider()`: config-driven selection. |
| `app/ai/tools.py` | 187 | **The typed tool registry** — the agent's only way to touch the world. 12 tools: `get_incident`, `get_service`, `get_topology`, `get_impact_radius`, `query_logs` (redacts untrusted messages before return), `query_metrics`, `compare_metrics` (current-vs-baseline + anomaly verdict), `get_deployments`, `get_health`, `get_timeline`, `get_related_incidents`, `get_evidence`. `list_tools()` self-describes for the UI. Results are JSON-safe, size-truncated (`MAX_TOOL_RESULT_CHARS = 4000`). |
| `app/ai/investigator.py` | 367 | **The agent loop** (detailed in §5.6): bounded evidence-collection skeleton, 2 LLM calls, deterministic fallback, temporal consistency checks, persistence of hypotheses/evidence/remediation/run/trace. `INVESTIGATION_SYSTEM_PROMPT` binds the untrusted-data rule. `_data_block()` wraps telemetry as DATA (parseability-preserving trimming). `InvestigationResult` dataclass (now with a proper `duration_ms` field). Loop safety: tool-call cap, per-tool repeat tracking, wall-clock budget. |

### 4.4 Backend tests

| File | Lines | What it covers |
|---|---|---|
| `tests/conftest.py` | 14 | Sets `ALETHEIA_DATABASE_URL` to a **unique per-session temp DB** before any app import (the app engine binds at import time). Guarantees zero state leakage between pytest runs — this exists because a resolved incident from a previous run once leaked into the next run's bootstrap check. |
| `tests/test_ingestion.py` | 77 | Normalization (lowercase severity, epoch timestamps, missing fields → None, non-dict → None), malformed-batch counting (never crashes), deduplication (same content twice → 1 stored + 1 counted duplicate), out-of-order events, defensive metadata handling. |
| `tests/test_metrics_topology.py` | 77 | Baseline computation over synthetic series; anomaly detection on spikes (z > 3, explanation contains the actual values) and on stable series (no anomaly); **decrease detection** (cache-hit collapse → negative z); EWMA math; topology downstream/upstream; impact radius propagation (orders-db → payments/orders/gateway); descendants; propagation-path stages. |
| `tests/test_security_ai.py` | 63 | Secret-key redaction (api_key/password/client_secret), secret-value redaction (JWT), PEM block redaction (body removed), nested metadata, injection-marker detection (positive + negative), quarantine explanation, mock determinism (same input → same output), mock output contains no secrets, remediation whitelist excludes dangerous verbs (shutdown, rm -rf, format, exec). |
| `tests/test_smoke.py` | 73 | Full in-process E2E via FastAPI TestClient: health; bootstrap (10 services, 1 incident); investigation (completed, ≥1 hypothesis, root cause present); agent trace (≥5 calls); remediation flow (**blocked without approval** → approve → execute → verify → postmortem sections); evaluation benchmark (5 scenarios, RC accuracy ≥ 0.6 quality bar). |
| `tests/live_qa.py` | 133 | 9 checks against a **running** server: overview data-driven; services+topology (10/10 nodes/edges, impact radius); log filters (service/severity/search); metrics series+anomalies; full lifecycle (investigate → 404-free trace → blocked → approve → execute → verify → postmortem); injection quarantine with `[REDACTED]` secret + `_quarantine` flag (uses a **relative** timestamp — an earlier fixed timestamp aged out of the search window and taught us this lesson); malformed batch resilience; evaluation suite; settings+tools registry. |
| `tests/e2e_directive90.py` | 170 | The atomic 20-step end-to-end scenario from the build directive §90, each step asserted: deployment exists → DB metrics degraded (peak >1000ms) → payments latency rose → orders errors rose → incident detected → correlated (category+4 services) → timeline (≥5 entries **including deployment kind** — tightened after a real gap was found) → topology downstream impact → AI investigates (31 calls) → evidence (≥5 rows) → hypotheses (≥2) → root cause ranked #1 with correct concept match → remediation proposed → approval pending → execution blocked → approved+executed → verification measured + status transition → postmortem (all sections + root cause present) → trace (≥20 calls, 0 errors) → evaluation recorded. |
| `tests/adversarial.py` | 188 | 13 attacks against a running server: non-array body; 5000-event bulk batch; 4 kinds of invalid timestamps; unknown IDs across 7 endpoints (found and fixed a 200-instead-of-404 bug on agent-run traces); double approve/execute idempotency; reject-then-execute blocked; verify-without-remediation; dangerous/empty actions → 400; extreme/negative/oversized query params; unicode + control chars + RTL override chars; injection in every field (secret still redacted, system intact); 3× repeated investigation; postmortem twice. |

### 4.5 Frontend

React 18 + TypeScript + Vite + Recharts, hash routing, dark SRE design system (§8).

| File | Lines | What it is |
|---|---|---|
| `src/api/client.ts` | 19 | `apiGet`/`apiPost` fetch wrappers with error surfacing; base URL from `VITE_API_BASE` or `http://localhost:8010`. |
| `src/types.ts` | 212 | Full TypeScript mirrors of all backend response shapes: TelemetryEvent, ServiceInfo, TopologyData, Anomaly, Incident, TimelineEntry, EvidenceItem, Hypothesis, InvestigationResult, Remediation, Verification, Postmortem, AgentRun, ToolCallEntry, EvaluationReport, OverviewData, Deployment, MetricSeries, SettingsInfo. |
| `src/hooks.ts` | 52 | `useApi` (cancellable fetch with refresh via tick counter), `useHealth` (top-bar poll). |
| `src/App.tsx` | 80 | AppShell: TopBar (env, health status, SYNTHETIC DEMO pill), Sidebar (11 nav items), `<Outlet/>`; `ErrorBoundary` via `useRouteError`. |
| `src/main.tsx` | 54 | Hash router wiring all 12 routes; StrictMode; global styles import. |
| `src/styles.css` | 319 | The design system: CSS variables (GitHub-dark-like palette), topbar/sidebar/layout, stat cards, 20+ badge variants (severity/status/approval/verification), buttons, tables, evidence items, hypothesis cards, timeline with kind-colored nodes, topology SVG styles, loading/empty/error states, responsive grid collapse. |
| `src/views/Overview.tsx` | 99 | 4 stat cards (active incidents, gateway error rate, p95, anomaly count) — all computed server-side from stored telemetry; active incident list; anomaly explanations; recent deployments table. |
| `src/views/Incidents.tsx` | 57 | Incident table: ID/title/severity/status/confidence/category/detected/affected services. |
| `src/views/IncidentDetail.tsx` | 354 | **The centerpiece screen**: header (severity/status/timestamps/correlation confidence); AI Investigation panel (run button, run metadata with DEMO MODE pill, root-cause card, alternatives with evidence); Remediation panel (per-action reason/expected effect/risk, approval badges, Approve/Reject/Execute buttons, verify button); Verification panel (outcome badge + per-metric evidence); Timeline (kind-colored entries); Evidence list (kind + description); Agent runs with expandable full tool-call traces; Postmortem panel (generate + copy markdown). |
| `src/views/Services.tsx` | 44 | Service table with kind badges, color-coded error rates, dependencies/dependents, descriptions. |
| `src/views/Topology.tsx` | 139 | Interactive SVG dependency graph: layered layout computed via longest-path depth algorithm, bezier edges (dashed = non-critical), nodes colored by kind (database purple, external amber), red border for incident-affected services, click-to-inspect relationships panel. |
| `src/views/Logs.tsx` | 106 | Log explorer: service/severity/search/time filters, expandable rows showing raw metadata/trace/source, severity-colored, live counts. |
| `src/views/Metrics.tsx` | 108 | Metric explorer: service+metric selectors (per-service sensible defaults), Recharts line with red anomaly ReferenceDots, and a "Why this was flagged" card quoting the anomaly explanations. |
| `src/views/Deployments.tsx` | 43 | Deployment table (time/service/version/commit/actor/notes). |
| `src/views/Investigator.tsx` | 115 | Agent observability screen: incidents with their latest root cause; agent-run table (provider/model/LLM calls/tokens/status); click-through full trace (seq/tool/args/duration/status/result). |
| `src/views/Postmortems.tsx` | 59 | Postmortem list with copy + download-as-markdown buttons. |
| `src/views/Evaluations.tsx` | 118 | Benchmark runner: aggregate stat cards (RC/services/remediation/recovery rates), per-scenario table with pass/miss badges, and a **full-transparency predicted-vs-known table**. |
| `src/views/Settings.tsx` | 102 | Runtime config: provider/model/mode (with demo-mode explanation), remediation mode + agent limits, ingestion health stats (accepted/duplicates/malformed), and the full agent tool registry. |
| `eslint.config.js` | — | Flat ESLint config: `@eslint/js` recommended + `typescript-eslint` recommended + react-hooks rules-of-hooks; unused-vars with `^_` pattern. |

### 4.6 Documentation

| File | Content |
|---|---|
| `README.md` | Project pitch, capability table, quick start, Docker, LLM enablement, repo layout, tests, honest limitations. |
| `docs/ARCHITECTURE.md` | Mermaid system overview, telemetry flow, incident lifecycle states, anomaly-detection math + the failure story of mean/stddev, rule engine, agent loop, the AI-vs-deterministic split table, provider abstraction, remediation control, verification math, evaluation isolation, self-observability. |
| `docs/SECURITY.md` | 9-row threat model table (injection, secret leakage, uncontrolled remediation, command execution, API abuse, data poisoning, alert storms, unbounded loops, fake success), trust boundaries, remediation safety, what's intentionally absent, test coverage map. |
| `docs/EVALUATION.md` | Benchmark purpose, scenario table with ground truth, method, scoring weights, results (5/5 with per-scenario table), how the ranking bug was found and fixed, and a prominent limitations section. |
| `docs/DEMO.md` | 10 scripted demos + 2 bonus (benchmarks, live injection attack), each with exact steps and expected output. |
| `docs/INCIDENT_MODEL.md` | ER diagram + every entity's fields and lifecycle semantics. |
| `docs/AI_INVESTIGATION.md` | Role split, the loop, the ranking formula, hallucination controls, loop safety, stopping criteria, limitations. |
| `docs/RESUME_NOTES.md` | Concise description, real stack, 7 strongest features, actual metrics with caveat, 3 resume bullets, talking points. |
| `docs/INTERVIEW_GUIDE.md` | 18 architecture questions with defensible, codebase-grounded answers. |
| `docs/adr/ADR-001…008` | Modular monolith · synthetic environment · SQLite local-first · rule+AI hybrid · provider abstraction · controlled remediation · evidence-first RCA · evaluation framework. Each: context → decision → consequences. |
| `CONTRIBUTING.md` | Dev setup, PR checks, the repo's 5 engineering rules, how to add a rule/tool. |
| `CHANGELOG.md` | v0.1.0 with everything added + the dev-visible bug fixes. |
| `BUILD_STATUS.md` | Every directive checklist item with the verification evidence. |
| `LICENSE` | MIT. |

### 4.7 Root, Docker, and CI files

| File | Content |
|---|---|
| `.gitignore` | Python bytecode/venvs/caches, DB files, `.env` (with `!.env.example` carve-out), node_modules/dist, IDE/OS junk, graphify working state. |
| `backend/pyproject.toml` | Dependencies + dev extras + **ruff config** (full rule set, B008 ignored as the canonical FastAPI DI idiom) + pytest paths. |
| `backend/Dockerfile` | `python:3.12-slim`, dependency-only layer copy for caching, non-root `sentinel` user, env-driven DB URL, uvicorn on 8000. |
| `.github/workflows/backend.yml` | On backend paths: ruff (full set) → mypy → pytest (excluding live suites) → docker build → container health smoke (`curl /api/health` must return `status:ok`). |
| `.github/workflows/frontend.yml` | On frontend paths: npm ci → eslint → tsc → vite build. |

---

## 5. Every Mechanism, Explained in Detail

### 5.1 Telemetry ingestion pipeline

**Path:** `POST /api/telemetry` → raw-body parse → per-event security pass → `ingest_events()`.

1. **Permissive raw-body parsing.** The endpoint reads `await request.json()` itself. A
   non-array body returns a counted malformed entry, not a 422. This was a deliberate
   change: originally a `list[TelemetryEventIn]` parameter, which made FastAPI reject the
   whole batch on one bad entry — the opposite of the resilience requirement.

2. **Security pass (per event, before storage):** `redact_mapping()` cleans the metadata
   tree (secret-looking keys and values → `[REDACTED]`); `contains_injection_markers()`
   checks the message and metadata string; flagged events get
   `metadata._quarantine = true` and a `_quarantine_reason` explaining that the content is
   DATA and will never be passed to the agent as instructions.

3. **Normalization** (`normalize_event`): timestamp parsing accepts ISO strings (with `Z`
   handling and naive→UTC promotion), epoch ints/floats, and datetimes; severity is
   uppercased and validated against the 5-level set (invalid → INFO); event_type and
   message are length-capped; non-dict metadata is preserved defensively as
   `{"_original_metadata": "…"}` rather than dropped.

4. **Deduplication:** `dedup_hash = sha256(timestamp|service|event_type|message|metadata)`
   — 40 hex chars. A process-level `_seen_hashes` set (lazy-loaded from the DB on first
   use) makes duplicate detection O(1) per event. Duplicates are skipped and counted.
   (During development this cache also bit us in tests — it persists across DB deletion
   within a process — which is why `conftest.py` now creates unique per-session DBs and
   live suites restart the server.)

5. **Failure accounting:** every batch writes an `IngestionStats` row (received/accepted/
   duplicates/malformed + up to 20 parse-error samples). The Settings screen surfaces
   cumulative counts. A 5000-event adversarial batch ingests cleanly.

**Design guarantee:** no malformed input can crash a batch — every stage is exception-
guarded and failures become data (counts + samples).

### 5.2 Anomaly detection — the math and why

`detect_anomalies(series, service, metric)` in `metrics_engine.py`:

- **Windowing:** current = last 5 minutes; baseline = the 60 minutes before that.
  (Baseline is intentionally long so a developing incident can't dominate its own
  baseline — see below.)
- **Robust statistics:** baseline median and MAD (median absolute deviation), scaled to a
  stddev-equivalent: `robust_sigma = max(MAD × 1.4826, ε)`.
- **Score:** `z = (current_mean − median) / robust_sigma` — the Iglewicz-Hoaglin modified
  z-score. Flagged when `|z| ≥ 3.0`.

**Why not mean/stddev?** Measured, not theorized: during a connection-pool scenario,
mean/stddev over a 30-minute window diluted a 145% change (40→98 connections) to z≈2.5 —
below the threshold — because the incident's own ramp polluted the baseline tail.
Median/MAD on the same data gave z≈35.9. Robust statistics are specifically resistant to
exactly this contamination pattern. This choice is documented in ARCHITECTURE.md and the
failure story is an interview talking point.

**Interpretability contract:** every anomaly carries an explanation with the actual values:

> `orders-db/db_connections increased from 41.2 baseline to 98.7 (z=16.63, 140% change over last 5m vs prior 60m baseline)`

No fabricated baselines — the numbers come from the series itself.

### 5.3 Service topology and impact propagation

The graph is 10 nodes / 10 directed edges, persisted in the DB (`Service`, `Dependency`)
and loaded into `TopologyGraph`. The four queries that power incident reasoning:

- `downstream(X)` / `upstream(X)` — direct dependencies/dependents.
- `descendants(X)` — transitive closure of dependencies (what X needs).
- `impact_radius(X)` — transitive closure of dependents (who breaks when X breaks).
  Example, verified by tests: `impact_radius("orders-db")` = {orders-db, payments-service,
  orders-service, api-gateway}.
- `propagation_path(X)` — staged BFS: root → direct_impact → downstream_impact →
  user_impact. This feeds the UI's causal narrative: *DB pool exhaustion → payments
  timeout → orders fail → gateway errors → users can't place orders*.

The correlation rules and the AI investigator both use these queries to separate causes
(near the root of the propagation) from symptoms (the impact radius).

### 5.4 The correlation rule engine

**Philosophy:** incidents are *created* by deterministic rules over computed facts, never
by the LLM. Five rules, each an isolated class with a shared read-only
`CorrelationContext` (cached anomaly scan over all service×metric pairs, error logs,
deployments, topology):

| Rule | Trigger logic (abbreviated) | Category / severity |
|---|---|---|
| `DatabaseExhaustionRule` | DB latency anomaly AND (connections anomaly (+0.2) AND/OR timeout/exhaustion error logs from dependents (+0.15)); floor confidence 0.6 | database_exhaustion / high |
| `DeploymentRegressionRule` | Deployment in last 2h whose service shows anomalies; confidence adjusted −0.25 if first anomaly predates the deployment (temporal check) | deployment_regression / high |
| `ResourceSaturationRule` | memory/CPU (and GC) anomalies + latency corroboration; memory-primary → memory_leak category | resource_saturation / memory_leak / high |
| `CacheFailureRule` | cache_hit_rate DECREASE (z<0 — direction-aware) + backing-store load anomalies | cache_failure / medium |
| `DependencyTimeoutRule` | the *earliest* latency anomaly across all services; corroborated by dependents' anomalies (+0.1 each); requires dependents to exist (else no propagation = no incident) | dependency_timeout / medium |

`run_correlation()` evaluates all rules, swallows per-rule exceptions (one broken rule
can't kill detection), sorts results by confidence. `detect_incidents()` then creates
incidents — **with dedup**: an open incident with the same category and overlapping
affected services suppresses a new one. That's the alert-storm guarantee: DB latency +
connection saturation + payment timeouts + order failures + gateway errors = ONE incident.

### 5.5 Incident lifecycle and the timeline

States: `open → investigating → mitigated → resolved`, each transition earned:

- `open → investigating`: an investigation run completed (hypotheses persisted).
- `investigating → mitigated`: an approved remediation executed in the simulation.
- `mitigated → resolved`: **only** `verification.outcome == "recovered"`. No other code
  path writes `resolved`.

`build_timeline()` assembles, sorted chronologically: deployment events (both from
incident signals and from the deployments table within 30 minutes pre-incident — this
inclusion was a real gap found and fixed during the super-final pass), ERROR/CRITICAL
logs for affected services, the detection event, remediation proposals and executions,
and verification outcomes. Each entry has a `kind` (deployment/log/incident/remediation)
that the UI renders as a color-coded timeline node.

### 5.6 The AI investigator — every step

The loop in `investigator.py` is a **bounded evidence-collection skeleton**, not open-ended
ReAct wandering:

1. **UNDERSTAND** — `get_incident`, `get_topology` (traced tool calls).
2. **COLLECT EVIDENCE** — for each affected service (≤6): `get_service`, then
   `compare_metrics` for **every** metric that service has, then `query_logs` (ERROR,
   last 60 min, redacted). Every call is traced with duration and status. *(An
   indentation bug here once recorded only the last metric per service — the benchmark
   caught it, see §10.)*
3. **TOPOLOGY** — `get_impact_radius` on the primary affected service.
4. **DEPLOYMENTS** — `get_deployments` (last 6h).
5. **FORM HYPOTHESES** — ONE LLM (or mock) call. The prompt = the investigation system
   prompt (untrusted-data rules) + the requested JSON schema + `_data_block("collected
   evidence", …)` containing incident (minus signals), metric comparisons (≤10), error
   logs (≤10), topology impact, deployments — all wrapped as DATA.
6. **TEST/RANK** — hypotheses get a temporal-consistency flag; sorted by confidence.
7. **RECOMMEND** — a SECOND LLM call with `_data_block("top hypothesis", …)` +
   deployments + incident signals; must return one action from the whitelist.
8. **PERSIST** — up to 6 `Hypothesis` rows (rank + verdict most_likely/considered),
   up to 12 metric `Evidence` rows (with current-vs-baseline text), up to 10 redacted
   log `Evidence` rows, a `Remediation` proposal (status=proposed, approval=pending),
   the `AgentRun` (provider/model/tokens/stop reason), and every `ToolCall`.
9. **Loop safety checkpoint** — if the tool-call cap tripped, `status=stopped_limit`
   with a recorded reason the UI displays.

**Deterministic fallback:** if the provider returns nothing parseable, hypotheses are
derived directly from the collected anomalies (statements naming the real service and
metric). The investigation never dead-ends when AI is unavailable — the platform keeps
functioning.

### 5.7 Hypothesis ranking — the formula

```
confidence = 0.4
           + min(|z|, 8) / 25          # anomaly strength, capped so one extreme metric can't dominate
           + category_bonus            # +0.15 if metric agrees with the correlation rule's category
           + KIND_PRIOR[kind]           # causal-kind prior (see table)
```

| Kind | Prior | Rationale |
|---|---|---|
| connection pool exhaustion | 0.30 | root-state kind |
| memory pressure / leak | 0.25 | root-state kind |
| cache failure | 0.25 | root-state kind |
| auth validation failure | 0.25 | root-state kind |
| provider rate limiting / dependency timeout | 0.25 | root-state kind |
| work-queue backlog saturation | 0.15 | intermediate |
| database capacity saturation | 0.10 | derived symptom |
| latency degradation | 0.05 | generic symptom — always present |

**Deployment-regression hypothesis:** gets a strong prior (0.95 base) only when the
deployed service's OWN **state** metrics (not error/latency symptoms, which appear in
every scenario) are anomalous — the `linked` condition. This rule was learned the hard
way (§10).

The score intentionally exceeds 1.0 for ranking differentiation; downstream persistence
clamps to ≤0.99 for display. Confidence values are labeled everywhere as **engineering
estimates**, never scientific probabilities.

### 5.8 The mock LLM provider — deterministic reasoning

`MockProvider.complete()` inspects the prompt for the requested schema
(`"hypotheses"` or `"recommended_action"`) and produces deterministic output:

- `_derive_hypotheses`: parses the `collected evidence` DATA block (anomaly z-scores,
  explanations, deployments, incident category). Maps each anomalous metric to a
  causal *kind* (`kind_for`), merges per (service, kind) keeping the max confidence and
  unioning evidence, adds the deployment-regression hypothesis with the state-metric
  link rule, sorts, returns top 4. Same evidence in → same hypotheses out, always.
- `_derive_action`: parses the `top hypothesis` DATA block — **never the prompt
  boilerplate** (which lists all whitelisted actions and would short-circuit every
  keyword match — this was a real bug, §10) — and maps: connection/exhaust →
  increase_connection_pool; cache → clear_cache; memory/leak → restart_service;
  regression/deployment → rollback_deployment; else default safe restart.

This makes the entire platform reproducible without an API key, which is what lets CI
run the full lifecycle and what makes the benchmark numbers meaningful (same seed →
same result).

### 5.9 Controlled remediation — the safety spine

Three independent layers:

1. **Whitelist** (`ALLOWED_ACTIONS`): rollback_deployment, restart_service, scale_service,
   clear_cache, increase_connection_pool, disable_feature_flag. `propose_remediation()`
   raises `ValueError` (→ API 400) for anything else. Adversarial tests confirm `rm -rf /`,
   `shutdown`, `format c:`, `exec`, and empty strings are all rejected.

2. **Mode matrix** (`remediation_mode`): `analysis` and `recommend` forbid execution
   entirely; `approval_required` (the default) blocks execution until approval;
   `simulation`/`execute` progressively relax. Enforced server-side in
   `execute_remediation()` — the UI cannot bypass it.

3. **Approval state machine:** `pending → approved/rejected`, with approver identity
   recorded. Execution without approval returns
   `{"status": "blocked", "result": "approval required before execution"}` — verified live
   in three separate test suites.

Execution acts **only on the simulation**: it generates post-remediation recovery
telemetry (§5.10's input), writes a `remediation_applied` event, records
initiator/timestamp/reason/params/expected-effect/actual-result, and moves the incident to
`mitigated`. There is **no subprocess, shell, or host-filesystem code path anywhere in
the backend** — verified by grep and by the security review.

### 5.10 Recovery verification — measured, never claimed

`verify_recovery()` per incident:

1. Collects the target metrics (from incident signals, falling back to error_rate/p95 of
   affected services).
2. Splits each metric's series at the remediation timestamp: `pre` (up to 30 points) vs
   `post` (needs ≥3 samples else `unknown` — honest about insufficient data).
3. Computes baseline (robust), pre-peak, post-mean, and
   `gap_closed_pct = (peak − post_mean) / (peak − baseline)`.
4. Per-metric outcome: `recovered` if ≥60% of the gap closed, `partial` beyond a looser
   band, else `not_recovered`; each with the real numbers in evidence:
   `orders-db/db_latency_ms: peak 1847.8 -> post-remediation avg 415.2 (baseline 860.5; 145% of gap closed)`
5. Aggregate outcome: all recovered → `recovered`; some → `partial`; none →
   `not_recovered`; nothing measurable → `unknown`.
6. **Only** a `recovered` outcome writes `incident.status = resolved` +
   `resolved_at`. This is the no-fake-success guarantee: the platform physically cannot
   claim recovery without telemetry proving it.

### 5.11 Postmortem generation

`generate_postmortem()` reads *only stored records* — incident, evidence rows,
hypotheses (with evidence_for), remediations, verifications — and emits 13 markdown
sections: Summary, Impact, Timeline (deployments, log evidence, detection, executions,
verifications), Root Cause (top hypothesis + its evidence, or an explicit "not
determined"), Contributing Factors (alternatives + metric deviations), Detection,
Response, Mitigation, Recovery (per-metric gap-closure numbers), What Went Well, What
Went Poorly (honest: unresolved at writing time, synthetic-window dependence),
Preventive Actions (category-conditioned), Follow-up Items (checklist with owners).
`generated_by` records rule-based vs LLM. Nothing in the template can render a
fabricated fact because every line template references a queried field.

### 5.12 The evaluation harness

- **Isolation:** `_isolated_session()` builds a fresh in-memory SQLite (StaticPool,
  same-thread) per scenario. One scenario's telemetry can never contaminate another's
  baseline windows — this mattered: with a shared DB, the first scenario's stale peaks
  poisoned later scenarios' anomaly detection (found via debugging RC=0 with correct
  hypotheses present).
- **Seeding:** 50 minutes of healthy baseline + a 15-minute causal incident window +
  the deployment row, then the incident record bound to `scenario_id` (ground truth).
- **Full pipeline per scenario:** investigate (wall-clocked) → take the agent's proposed
  remediation (or propose from its recommendation) → harness approves (as "eval-harness")
  → execute → verify.
- **Scoring** (`score_case`): root-cause correctness via `_concept_match` (every declared
  ground-truth concept must appear in the top hypothesis statement), affected-service
  overlap ≥ expected−1, remediation ∈ scenario's acceptable set, recovery verified,
  evidence sufficiency. Weighted score: RC 0.4, services 0.2, remediation 0.2, recovery
  0.1, evidence 0.1.
- **Persistence:** `EvaluationCase` rows go to the main DB; the response carries
  per-scenario results + aggregate. The Evaluations UI shows both plus the
  predicted-vs-known comparison for full transparency.

### 5.13 Security mechanisms

| Mechanism | Where | Detail |
|---|---|---|
| Secret redaction | ingestion + evidence persistence + tool results | 5 key-pattern families, 4 literal-value patterns, PEM blocks; nested-dict recursion; verified by unit + adversarial tests |
| Prompt-injection quarantine | ingestion | 6 marker phrases → `_quarantine` + standardized reason; the system prompt's DATA-block rule; the mock provider is structurally immune (deterministic, no prose obedience) |
| Untrusted-data boundary | investigator prompt construction | `_data_block()` wraps telemetry with explicit markers; sizes trimmed while preserving JSON parseability (learned: raw slicing broke parsing — §10) |
| Action whitelist + approval gate | remediation | server-enforced; 400 on dangerous verbs; blocked execution pre-approval |
| No host execution | whole backend | zero subprocess/shell calls — grep-verified and stated in SECURITY.md |
| Input validation | API layer | typed query params with limits; permissive ingestion that counts rather than trusts; 404 on unknown IDs (fixed post-adversarial) |
| Alert-storm defense | incident dedup | category + service-overlap suppression |
| Loop safety | agent | 40-call cap, repeat tracking, wall-clock budget, recorded stop reasons |
| Measurement integrity | benchmark isolation + verification engine | isolated scenario DBs; recovery only from measured telemetry |
| Credential hygiene | config | env-only (`ALETHEIA_LLM_API_KEY`); `.env` git-ignored; repo-wide secret scan clean |

### 5.14 Agent observability — the platform observing itself

Every investigation writes an `AgentRun` (provider, model, status, start/finish, token
estimates, LLM request count, summary, stop reason) and one `ToolCall` row per tool use
(seq, tool name, args, result status, duration_ms, result summary, error). The
Investigator screen and the incident detail page render these as a flight-recorder
table. Token counts are provider-reported for OpenAI-compatible providers and honest
length/4 estimates for the mock — the UI labels estimates as such. Investigation
duration, tool-call counts, and failure counts also feed the evaluation cases, so agent
cost/latency is a benchmarked dimension, not an afterthought.

---

## 6. The Five Benchmark Scenarios — Full Specifications

Every scenario is a causal story: trigger → primary telemetry change → propagation →
secondary effects, with declared ground truth.

### 6.1 `db_connection_exhaustion` — Database connection pool exhaustion after deployment
- **Trigger:** payments-service v2.4.1 deployment lowers pool recycle interval; connections leak under load.
- **Timeline:** deployment → DB latency ramps (45→1800ms, ramp 5min) → connections (40→100, ramp 4min) → slow queries (2→60) → payments p95 (180→950) and errors (0.4%→22%) → orders errors (0.3%→18%) → gateway errors (0.2%→9.5%).
- **Logs (with trace IDs):** pool warnings at 82%/95%, `connection_exhausted` at 100/100, payment `database_timeout`s, orders `dependency_timeout` → `order_failed`, gateway 5xx spike.
- **Ground truth:** root cause concepts `["orders-db", "connection", "exhaust"]`; affected `[orders-db, payments-service, orders-service, api-gateway]`; acceptable remediations: rollback/increase-pool/restart/scale.
- **This is the flagship** — auto-seeded at startup and the subject of the 20-step E2E.

### 6.2 `deployment_regression_auth` — auth-service v1.9.2 rejects valid tokens
- **Trigger:** token header parsing change rejects ~30% of valid tokens.
- **Signature:** auth_failure_rate 0.5%→31% within 2 minutes of deployment; gateway 401s spike; **downstream services stay healthy** (orders/payments error rates ≈ baseline) — the topology asymmetry that distinguishes this from a cascading failure.
- **Ground truth:** concepts `["auth-service", "regression"]`; acceptable: rollback / disable_feature_flag.

### 6.3 `cache_failure_inventory` — inventory cache outage
- **Trigger:** Redis cluster unreachable; reads fall through to inventory-db.
- **Signature:** cache_hit_rate 92%→3% (ramp 1min — a DECREASE, direction-aware rule), inventory p95 45→380ms, inventory-db latency 12→210ms and CPU 30→93% (the backing store absorbing 6× read load), then orders/gateway degradation.
- **Ground truth:** concepts `["inventory", "cache"]`; acceptable: restart/clear-cache/scale.

### 6.4 `memory_leak_orders` — unbounded in-process cache in orders-service v3.1.0
- **Trigger:** cache refactor retains session objects without eviction.
- **Signature:** memory 420→1950MB over 9 minutes (monotonic growth), GC pauses 15→400ms, then latency/error degradation; payments stays healthy (isolates the leak to orders).
- **Ground truth:** concepts `["orders-service", "memory"]`; acceptable: rollback/restart/scale/clear-cache.

### 6.5 `dependency_timeout_email` — external email provider rate limiting
- **Trigger:** provider throttles; per-send latency 250ms→8s.
- **Signature:** send latency ramps first (the earliest anomaly — what DependencyTimeoutRule keys on), notification queue 4→900 and p95 300→7500ms, orders slows on the notification step (non-critical dependency → moderate errors, latency-dominant), gateway p95 150→400.
- **Ground truth:** concepts `["email-provider", "rate limit"]`; acceptable: restart/disable-flag/scale.

**Scenario integrity rules enforced by design:** metrics ramp then plateau (incident
unmitigated until remediation); recovery windows decay peak→baseline over
`recovery_minutes` (verification's input); healthy services keep running background
telemetry (so "unaffected" is observable, not assumed).

---

## 7. The API Surface — All 34 Endpoints

Base: FastAPI, OpenAPI docs at `/docs` (34 paths validated).

**Health:** `GET /api/health` — status/app/env/synthetic-flag/time.

**Services & topology:** `GET /api/services` (with live error rates + deps) ·
`GET /api/services/{name}/metrics` (current vs previous window) · `GET /api/topology`
(nodes+edges) · `GET /api/topology/impact/{service}` (impact radius + staged propagation).

**Telemetry:** `POST /api/telemetry` (permissive batch, redaction, quarantine, dedup,
stats) · `GET /api/telemetry/stats` (cumulative accepted/duplicates/malformed).

**Logs:** `GET /api/logs` (service/severity/event_type/search/trace_id/minutes/limit/
offset; returns total+items) · `GET /api/logs/stats` (severity counts).

**Metrics:** `GET /api/metrics` (service+metric series + anomaly explanations).

**Deployments:** `GET /api/deployments` (window-filtered).

**Incidents:** `GET /api/incidents` · `POST /api/incidents/detect` (run correlation →
create deduped incidents) · `GET /api/incidents/{id}` · `/timeline` · `/evidence` ·
`/hypotheses` · `/remediations` · `POST /api/incidents/{id}/investigate` · `/remediate` ·
`/verify` · `/postmortem` · `GET /api/incidents/{id}/verifications`.

**Remediations:** `POST /api/remediations/{id}/approve` (approve/reject with approver) ·
`POST /api/remediations/{id}/execute` (mode+approval gated, simulation-only).

**Postmortems:** `POST /api/incidents/{id}/postmortem` · `GET /api/postmortems` ·
`GET /api/postmortems/{id}`.

**Agent:** `GET /api/tools` (registry self-description) · `GET /api/agent/runs` ·
`GET /api/agent/runs/{run_id}/trace` (404 on unknown — fixed post-adversarial).

**Evaluations:** `POST /api/evaluations/run` · `GET /api/evaluations`.

**Overview:** `GET /api/overview` — the dashboard aggregate (active incidents, affected
services, gateway error/latency, recent deployments, anomaly count + explanations) —
every value computed from stored telemetry.

**Settings:** `GET /api/settings` — provider/model/enabled/demo-mode/remediation-mode/
agent limits, reflecting runtime config.

---

## 8. The Frontend — Every Screen

Design language: a credible developer/SRE tool (GitHub-dark palette, monospace data
values, dense tables, color semantics: red=critical/error, amber=warn/partial,
green=ok/recovered, purple=AI/executed, blue=accent). Every view implements **loading,
empty, error, and normal states**.

1. **Overview** — 4 stat cards (active incidents w/ count of affected services; gateway
   error rate; gateway p95; anomaly count) + active-incident cards (severity/status
   badges, affected services) + "why flagged" anomaly explanations + recent deployments.
2. **Incidents** — full table with confidence and category columns; rows link to detail.
3. **Incident Detail** (354 lines, the centerpiece) — header strip; AI Investigation
   panel (run button → run metadata + DEMO MODE pill + root-cause card + ranked
   alternatives each with evidence); Remediation panel (action/reason/expected/risk +
   pending/approved/rejected/executed badges + Approve/Reject/Execute buttons + verify);
   Verification panel (outcome badge + per-metric evidence lines); Timeline (kind-colored
   nodes: deployment purple, log amber, incident red, remediation green); Evidence list
   (kind labels + descriptions); Agent runs with expandable traces (seq/tool/args/
   duration/status/result); Postmortem panel (generate/copy).
4. **Services** — table with kind badges, color-coded error rates, deps/dependents.
5. **Topology** — interactive SVG: layered layout (longest-path depth), bezier edges
   (dashed=non-critical), kind-colored nodes, red border for incident-affected, click
   → relationship inspector.
6. **Logs** — toolbar filters (service/severity/search/window), expandable rows with raw
   metadata/trace/source JSON, severity colors.
7. **Metrics** — service+metric selectors, Recharts line with red anomaly markers, and
   the "Why this was flagged" explanations panel.
8. **Deployments** — full history table.
9. **AI Investigator** — incidents with latest root causes; run table (provider/model/
   LLM calls/tokens/status); click-through complete trace.
10. **Postmortems** — rendered markdown + copy + download-as-`.md`.
11. **Evaluations** — run button; aggregate cards; per-scenario pass/miss table; the
    predicted-vs-known transparency table.
12. **Settings** — provider config + demo-mode explanation, remediation mode + agent
    limits, ingestion health counters, tool registry.

The top bar always shows environment, API status, and the `SYNTHETIC DEMO` pill (turns
`LIVE` only if the backend reports non-synthetic) — the no-fake-AI rule made visible.

---

## 9. The Database Schema — All 15 Entities

(SQLAlchemy 2.0 typed models; SQLite default, PostgreSQL-ready — no dialect-specific SQL.)

| Entity | Key fields | Purpose / lifecycle role |
|---|---|---|
| `Environment` | id, name | Named environment registry. |
| `Service` | id, name (unique), kind (service/database/external), description | Topology nodes. |
| `Dependency` | source, target, dep_type (depends_on/uses), critical | Directed topology edges. |
| `TelemetryEvent` | timestamp(idx), service(idx), environment, severity, event_type(idx), message, metadata_json, trace_id, dedup_hash(idx), raw_source | The universal normalized record; dedup_hash drives ingestion idempotency. |
| `MetricPoint` | timestamp(idx), service(idx), metric_name(idx), value | Raw metric samples — baselines/anomalies always computed, never stored as observed. |
| `Deployment` | timestamp(idx), service(idx), version, actor, commit, notes | First-class investigation evidence. |
| `Incident` | id (INC-XXXXXXXX), title, status, severity, confidence, category, started_at, detected_at, resolved_at, affected_services(JSON), signals(JSON), root_cause, root_cause_confidence, scenario_id | Lifecycle per §5.5; `scenario_id` binds ground truth. |
| `Hypothesis` | incident_id, statement, confidence, evidence_for(JSON), evidence_against(JSON), rank, verdict | Evidence-first RCA records. |
| `Evidence` | incident_id, kind (metric/log/deployment/topology/analysis), description, source_ref, observed_at, details | Every collected fact, queryable per incident. |
| `Remediation` | incident_id, action, target_service, params, reason, expected_effect, risk, status, approval_state, initiated_by, approved_by, executed_at, result | The action audit record — who/what/when/why/params/result. |
| `Verification` | incident_id, remediation_id, outcome, checked_metrics(JSON), evidence(JSON), checked_at | Recovery measurement; sole owner of the `resolved` transition. |
| `Postmortem` | incident_id, title, content_markdown, generated_by | The report. |
| `AgentRun` | incident_id, status, provider, model, started_at, finished_at, summary, input_tokens, output_tokens, llm_request_count, stop_reason | Self-observability + loop-safety evidence. |
| `ToolCall` | run_id, seq, tool_name, args, result_status, duration_ms, result_summary, error | The agent's flight recorder. |
| `EvaluationCase` | scenario_id, incident_id, known_root_cause, expected_services, predicted_root_cause, root_cause_correct, affected_services_correct, remediation_correct, recovery_verified, evidence_count, tool_calls, failed_tool_calls, investigation_duration_ms, score, details | Benchmark results. |
| `IngestionStats` | batch_id, received, accepted, duplicates, malformed, parse_errors(JSON) | Ingestion health (surfaced in Settings). |

---

## 10. Bugs Found and Fixed During Development

Every one of these was found by a real check (benchmark, adversarial suite, or a tool
run), not by reading code. This section exists because the evaluation harness earned
its keep.

| # | Bug | How found | Fix |
|---|---|---|---|
| 1 | **Evidence-loss indentation bug** — the `if isinstance(cmp_result...)` block was outside the metric loop, so only the LAST metric per service was recorded. The agent investigated with 4 data points instead of 19. | Benchmark RC=0 with correct keywords visible elsewhere; prompt inspection | Indentation fix; benchmark scores immediately jumped |
| 2 | **Baseline pollution** — mean/stddev z-score diluted a 145% change to z≈2.5 (below 3σ) because the incident ramp contaminated its own baseline window | Manual z computation during debugging (z=2.54 vs robust z=35.86) | Iglewicz-Hoaglin median/MAD modified z-score + 60-min baseline; documented with the failure story |
| 3 | **Evidence-block truncation** — `_data_block` raw-sliced JSON at 6000 chars, breaking parseability; the mock silently fell back to "undetermined cause" | Mock-output comparison between synthetic and real prompts | Parseability-preserving trimming (truncate long lists, never mid-JSON) |
| 4 | **Prompt-boilerplate action matching** — `_derive_action` keyword-matched the WHOLE prompt, which lists all whitelisted actions → `"rollback" in prompt` was always true → every scenario recommended rollback (cache/dependency scenarios scored remediation=miss) | Benchmark remediation=0.6 with visible wrong actions | Parse the `top hypothesis` DATA block only; remediation 0.6→1.0 |
| 5 | **Symptom-over-cause ranking** — deployment-regression hypotheses promoted whenever the deployed service showed high-z anomalies — but error-rate symptoms exist in EVERY scenario, so DB/memory scenarios got "Deployment regression: latency degradation" | Benchmark RC flip-flop while tuning the auth scenario | The state-metric rule: strong 0.95 prior only when the deployed service's own state metrics (connection/memory/cache/auth — not error/latency) are anomalous; all 5 scenarios then scored 1.0 |
| 6 | **Trailing-comma tuple bug** — `name = "resource_saturation",` made a class attribute a tuple | Custom AST scan (tuple-assignment detector) during the aggressive audit | Fixed + added the scan to the audit |
| 7 | **27 dead symbols** — unused imports/vars after refactors | ruff F401/F841 sweep | Auto-fixed; loop-safety tool calls preserved deliberately |
| 8 | **422 on malformed telemetry** — strict Pydantic list validation rejected whole batches; spec requires skip-and-count | Live QA malformed-batch check | Raw-body parsing + defensive per-event handling |
| 9 | **`timezone` NameError swallowed** — ingestion's epoch-timestamp path referenced `timezone` without importing it; the broad `except` hid it, silently returning None | Unit test: `normalize_event` returned None for a valid epoch timestamp | Import fix + the test now guards it |
| 10 | **Timeline missing deployments** — flagship timeline showed only log+incident kinds; the deployment (the causal trigger!) was absent | Super-final E2E tightened step 7 to require the deployment kind | Timeline now merges signals, the deployments table (30-min pre-window), plus remediation and verification events |
| 11 | **200 instead of 404** — `/api/agent/runs/{unknown}/trace` returned 200-empty | Adversarial unknown-ID attack | Run existence check → 404; test added |
| 12 | **mypy type errors (6)** — dict rebound to a `str` var in security.py, wrong provider annotations, tuple-keyed dict typed `dict[str,…]`, **double-rounding** (round 3 then round 2) in confidence, `getattr` monkey-patch for duration | First-ever mypy run (during the "are you sure?" pass) | All fixed properly; mypy now in CI |
| 13 | **~48 full-ruff findings** — ambiguous `l` variables, missing `raise … from exc`, import sorting, `datetime.UTC` modernization, stale lint directive | Full ruff rule set (previously only 6 rules) | Fixed; B008 deliberately ignored (canonical FastAPI DI); config committed |
| 14 | **Test bugs in our own suites** — E2E used a fixed timestamp that aged out of the log-search window (the "injection quarantine" flake); an unknown-ID check used GET on a POST-only route | Adversarial + live-QA flake investigation | Relative timestamps; correct methods; root causes documented |
| 15 | **State leakage between test runs** — a resolved incident from a prior run suppressed the next run's bootstrap check; the in-process dedup cache also outlived DB deletion | Live-QA overview=0 mystery | Unique per-session temp DBs in conftest; live suites restart the server fresh |

---

## 11. Verification Evidence — Everything Ever Measured

All results below are from fresh runs against the final code (backend `9cdd0cf`
lineage, committed 2026-09-02). Nothing is claimed without a command that produced it.

### Static analysis
- `ruff check app/` (full rule set: E,F,I,W,UP,B; B008 ignored as FastAPI idiom): **All checks passed**
- `python -m mypy app/ --ignore-missing-imports --no-strict-optional`: **no issues in 26 files**
- `npx eslint src`: **clean**
- `npx tsc --noEmit -p tsconfig.app.json`: **clean**
- `npm run build`: **succeeds**

### Test suites
- `python -m pytest tests/ -q`: **28/28 passed** (units: ingestion, metrics, topology, security, AI; smoke E2E incl. benchmark)
- `python tests/live_qa.py` (against a running server): **ALL 9 LIVE QA CHECKS PASSED**
- `python tests/e2e_directive90.py`: **20/20 directive E2E steps PASSED** (fresh server + fresh DB, atomic)
- `python tests/adversarial.py`: **13/13 attacks survived** (bulk 5000-event batches, invalid timestamps, unknown IDs, double approve/execute, reject-then-execute, unicode/control chars, injection in all fields, extreme params, repeated runs)

### Benchmark (deterministic mock mode, seeded)
- Root-cause accuracy **5/5** · affected-service accuracy **5/5** · remediation
  correctness **5/5** · recovery verification **5/5** · average scenario score **1.00**
- Reproduced identically across at least four separate runs (pytest, live QA, E2E, direct) —
  determinism verified, not assumed.
- **Honest framing (also in docs/EVALUATION.md):** this measures the deterministic
  pipeline against clean synthetic signals with known ground truth. It is a correctness
  and regression bar, NOT a claim of real-world RCA performance.

### Container
- `docker build -t Aletheia-backend ./backend`: succeeds
- Container `/api/health`: `{"status":"ok","app":"Aletheia","environment":"demo","synthetic":true}`
- **Full lifecycle executed inside a container**: investigate → root cause → approve →
  execute → verification `recovered` → postmortem containing the correct root cause.

### Hygiene
- Tracked-file scan: no `.env`, no DB files, no `node_modules`/`dist`, no logs/caches
- Secret-pattern scan: only intentional fixtures (redaction regexes, clearly-fake demo keys)
- No file >500KB tracked
- `git status`: clean tree; 10 commits with per-fix rationale

---

## 12. Known Limitations — Stated Plainly

1. **All telemetry is synthetic** — generated by seeded scenarios. Every result in this
   repo measures the pipeline against simulated, causally-coherent signals, not real
   production noise, multi-causality, or telemetry gaps. The UI says `SYNTHETIC DEMO`
   everywhere for this reason.
2. **Benchmark 5/5 is a sanity bar.** Real incidents are noisier; claiming real-world
   RCA skill from synthetic scores would be dishonest. The evaluation doc repeats this.
3. **The mock provider is deterministic logic, not a language model** — its "reasoning"
   is the documented heuristics (§5.7–5.8). The OpenAI-compatible path is implemented
   and schema-constrained but only its happy path + fallback is exercised (no live
   external key was used in this build).
4. **Single-process, single-writer SQLite.** Fine for the demo scale and CI; the schema
   and ORM are PostgreSQL-ready (no dialect-specific SQL), but concurrency behavior under
   multi-process load is untested.
5. **Temporal onset ordering is recorded but not fully exploited** — the ranking uses
   kind priors and category agreement; per-metric onset-time reasoning is a documented
   next step (noted in AI_INVESTIGATION.md).
6. **Frontend verified at the API and build level** — every route's data contract is
   exercised by live suites, but no automated browser-rendering test exists.
7. **Remediation is simulation-only by design** — no real infrastructure connector
   exists, and adding one would need its own whitelist, mode, and audit surface (per ADR-006).

---

## 13. How to Run Everything

```bash
# ── Backend (no API key needed) ─────────────────────────────
cd backend
pip install fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings httpx pytest ruff mypy
python -m uvicorn app.main:app --port 8010
# → API on http://localhost:8010 · OpenAPI docs at /docs
# Startup auto-seeds the synthetic environment + flagship incident.

# ── Frontend ─────────────────────────────────────────────────
cd frontend
npm install
npm run dev          # opens e.g. http://localhost:5174

# ── Docker ──────────────────────────────────────────────────
docker build -t Aletheia-backend ./backend
docker run -p 8000:8000 Aletheia-backend

# ── Optional: real LLM (any OpenAI-compatible endpoint) ─────
export ALETHEIA_LLM_BASE_URL=https://api.openai.com/v1
export ALETHEIA_LLM_API_KEY=...
export ALETHEIA_LLM_MODEL=gpt-4o-mini
# (absent these → deterministic mock mode, labeled DEMO MODE in the UI)

# ── Quality gates (what CI runs) ─────────────────────────────
cd backend
ruff check app/                                        # lint
python -m mypy app/ --ignore-missing-imports --no-strict-optional   # types
python -m pytest tests/ -q                             # 28 tests

# ── Live suites (need a running server; each wants a FRESH server+DB) ──
python tests/live_qa.py            # 9 live checks
python tests/e2e_directive90.py    # the 20-step directive E2E
python tests/adversarial.py        # 13 attack scenarios

# ── Frontend gates ───────────────────────────────────────────
npx eslint src && npx tsc --noEmit -p tsconfig.app.json && npm run build
```

**The 10-minute demo path:** Overview → Incidents → open the flagship incident →
Run investigation → review hypotheses/evidence/trace → Approve → Execute (simulated) →
Verify recovery (watch the measured gap-closure evidence) → Generate postmortem →
Evaluations → Run benchmark suite. Then try the live injection attack from
docs/DEMO.md and watch the system store it as inert, redacted data.

---

*This document describes the repository exactly as committed. Every claim above traces
to a command that was actually run; where something is untested or synthetic, it says so.*


