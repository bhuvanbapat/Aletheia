# Contributing to SentinelOps

## Development setup

```bash
# backend
cd backend
python -m venv .venv && .venv\Scripts\activate  # Windows (or source .venv/bin/activate)
pip install fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings httpx pytest ruff

# frontend
cd frontend
npm install
```

## Before opening a PR

Backend:
```bash
ruff check app/ --select F401,F841,F811,E711,B006   # must pass
python -m pytest tests/ -v                           # all tests must pass
```

Frontend:
```bash
npx tsc --noEmit -p tsconfig.app.json                 # must pass
npm run build                                         # must succeed
```

CI runs the same checks (`.github/workflows/`).

## Engineering rules this repo follows

1. **No fabricated data.** Every displayed metric comes from stored
   telemetry or the evaluation harness. Synthetic data is labeled as such.
2. **Evidence before conclusions.** Any RCA claim must reference collected
   evidence rows.
3. **Deterministic before AI.** Arithmetic, correlation, gating, and
   measurement are never delegated to an LLM.
4. **Safety is server-side.** Approval gates and whitelists live in the
   backend, not the UI.
5. **Tests prove claims.** If a PR says "fixed", a test demonstrates it.

## Adding a correlation rule

1. Subclass `CorrelationRule` in `app/incident_rules.py` (set `name`,
   `category`, `severity`, implement `evaluate`).
2. Add it to `DEFAULT_RULES`.
3. Add a benchmark scenario if the rule targets a new failure class, and a
   unit test for the rule's trigger conditions.

## Adding an agent tool

1. Implement it on `ToolRegistry` (`app/ai/tools.py`) returning plain
   JSON-safe structures (redact untrusted text).
2. Add it to `list_tools()` and `TOOL_NAMES`.
3. Extend the investigator's loop only if it serves the evidence story —
   the loop is intentionally bounded.
