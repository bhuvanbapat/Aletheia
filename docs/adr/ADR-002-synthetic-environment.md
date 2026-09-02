# ADR-002: Synthetic distributed environment

**Status:** Accepted

## Context
Demonstrating incident intelligence needs real causal telemetry, but
operating real infrastructure is out of scope and unsafe for a demo.

## Decision
Simulate a 10-service e-commerce system with a dependency graph and a
seeded telemetry generator that produces (a) healthy baselines and
(b) incident windows with causal stories: a root metric degrades first,
effects propagate via the topology, logs corroborate. Scenarios declare
ground truth (root cause, expected evidence, acceptable remediations)
which also powers the evaluation harness.

## Consequences
- Fully deterministic, reproducible demos and benchmarks.
- The simulation boundary also becomes the security boundary for
  remediation (ADR-006).
- Limitation (documented everywhere): results measure the pipeline
  against clean synthetic signals, not real-world noise.
