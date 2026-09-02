# ADR-008: Evaluation framework with known ground truth

**Status:** Accepted

## Context
"Does the AI actually find the right root cause?" cannot be answered by
reading its output — it needs ground truth and scoring.

## Decision
Five benchmark scenarios declare root cause, expected affected services,
expected evidence, and acceptable remediations. Each runs in an isolated
in-memory DB (no cross-contamination of baselines). Scoring is
concept-based matching plus service/remediation/recovery/evidence checks.
Results are real measurements against synthetic incidents and are
published with explicit limitations.

## Consequences
- Regression in ranking logic is caught by tests, not by vibes. During
  development the benchmark caught: evidence-loss indentation bug, z-score
  dilution, prompt-boilerplate action matching, and symptom-over-cause
  ranking — each fixed with a principled rule.
- 5/5 on clean synthetic signals is a sanity bar, not a production
  claim — stated plainly in docs/EVALUATION.md.
