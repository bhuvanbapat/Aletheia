# ADR-005: LLM provider abstraction

**Status:** Accepted

## Context
The platform must (1) run with zero credentials for demos and CI, and
(2) use real LLM reasoning when an endpoint is available. Different teams
use different OpenAI-compatible providers.

## Decision
`LLMProvider` protocol with two implementations:
`OpenAICompatibleProvider` (any `/chat/completions` endpoint — OpenAI,
vLLM, Ollama, LM Studio) and `MockProvider` (deterministic, parses the
evidence JSON embedded in prompts and derives hypotheses from real
collected values). Selection is by environment config only
(`SENTINELOPS_LLM_BASE_URL/API_KEY/MODEL`); the UI shows which mode is
active and labels mock results `DEMO MODE`.

## Consequences
- No-key demo path is first-class, not an afterthought.
- Token/cost tracking comes from provider usage fields when available;
  the UI shows honest estimates otherwise.
- The mock's "understanding" is limited to the heuristics we wrote —
  acceptable for deterministic benchmarks, documented in
  docs/EVALUATION.md limitations.
