# SentinelOps Evaluation Methodology

## Purpose

Measure whether the platform actually identifies correct root causes,
affects the right services, recommends acceptable remediations, and verifies
recovery — against incidents with **known ground truth**.

## Benchmark scenarios

| Scenario | Injected root cause | Ground-truth concepts | Acceptable remediations |
|---|---|---|---|
| `db_connection_exhaustion` | orders-db pool exhausted after payments-service v2.4.1 deployment | orders-db, connection, exhaust | rollback, increase pool, restart, scale |
| `deployment_regression_auth` | auth-service v1.9.2 rejects valid tokens | auth-service, regression | rollback, disable feature flag |
| `cache_failure_inventory` | inventory cache outage → inventory-db overload | inventory, cache | restart, clear cache, scale |
| `memory_leak_orders` | orders-service unbounded cache growth | orders-service, memory | rollback, restart, scale, clear cache |
| `dependency_timeout_email` | email provider rate limiting | email-provider, rate limit | restart, disable flag, scale |

Each scenario defines a causal story: trigger → primary telemetry changes →
propagation through the topology → secondary effects, with known expected
evidence and recovery behavior.

## Method

For each scenario (in an **isolated in-memory DB** — scenarios cannot
contaminate each other's baselines):

1. Generate 50 min healthy baseline telemetry, then a 15-min incident window
   from the scenario's causal profile.
2. Create the incident (category, affected services, signals).
3. Run the full pipeline: AI investigation → remediation proposal →
   human-approval (harness) → simulated execution → recovery verification.
4. Score against ground truth.

## Scoring

| Metric | Definition | Weight |
|---|---|---|
| Root-cause accuracy | top hypothesis matches every ground-truth concept | 0.4 |
| Affected-service accuracy | ≥ (expected − 1) of expected services identified | 0.2 |
| Remediation correctness | recommended action ∈ scenario's acceptable set | 0.2 |
| Recovery verification | verification outcome ∈ {recovered, partial} | 0.1 |
| Evidence sufficiency | ≥5 evidence rows collected | 0.1 |

Root-cause matching is concept-based (`_concept_match`): every declared
concept (e.g. "orders-db", "connection") must appear in the predicted
statement. Confidence values are engineering estimates, explicitly labeled
as such.

## Results (mock/deterministic mode, seeded)

Measured on 2026-09-02 by `python -m pytest tests/test_smoke.py -s` and
`POST /api/evaluations/run`:

| Metric | Result |
|---|---|
| Root-cause accuracy | **5/5 (100%)** |
| Affected-service accuracy | **5/5 (100%)** |
| Remediation accuracy | **5/5 (100%)** |
| Recovery verification rate | **5/5 (100%)** |
| Average scenario score | **1.00** |

Per-scenario:

| Scenario | RC | Services | Remediation | Recovery | Score |
|---|---|---|---|---|---|
| db_connection_exhaustion | ✓ | ✓ | ✓ | ✓ | 1.0 |
| deployment_regression_auth | ✓ | ✓ | ✓ | ✓ | 1.0 |
| cache_failure_inventory | ✓ | ✓ | ✓ | ✓ | 1.0 |
| memory_leak_orders | ✓ | ✓ | ✓ | ✓ | 1.0 |
| dependency_timeout_email | ✓ | ✓ | ✓ | ✓ | 1.0 |

Honest note on how this was achieved: mid-development the deployment-regression
hypothesis initially outranked true root causes when the deployment's service
merely showed error-rate symptoms (every scenario has those). The fix —
requiring the deployed service's own **state** metrics to be anomalous for
the 0.95 causal prior — is a real, principled ranking rule, and the
deployment-regression scenario now also scores 1.0.

## Limitations (important)

- These results measure the **deterministic pipeline against clean synthetic
  signals**. Real incidents are noisier, multi-causal, and telemetry is
  incomplete. A 100% here is a **smoke-test-grade sanity result**, not a
  claim of real-world RCA performance.
- The mock provider is deterministic logic over collected evidence. Real LLM
  behavior (and its failure modes) is out of these benchmarks' scope.
- Concept matching rewards naming the right concepts; a real grader might
  also want causal-mechanism explanation quality.
- Scenarios are seeded and reproducible; unseen scenarios are not measured.
