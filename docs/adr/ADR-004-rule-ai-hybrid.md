# ADR-004: Rule + AI hybrid architecture

**Status:** Accepted

## Context
Pure-LLM incident analysis hallucinates, cannot do reliable arithmetic,
and jumps from "errors" to "database". Pure rules cannot explain,
rank hypotheses, or write reports.

## Decision
Deterministic systems own anything requiring correctness: metric math,
z-scores, correlation, topology propagation, severity, approval gating,
recovery measurement. The AI owns reasoning-shaped work: hypothesis
generation, ranking rationale, recommendation, narrative. The rule engine
creates incidents; the agent investigates them — never invents them.
A deterministic fallback derives hypotheses from collected anomalies if
the LLM fails, so analysis never dead-ends.

## Consequences
- Every incident is grounded in computed facts; the LLM cannot fabricate
  a baseline or an incident that rules did not detect.
- The mock provider is itself deterministic evidence-based logic, which
  makes the whole pipeline reproducible without an API key.
- Ranking needed explicit causal priors (symptom kinds demoted below
  root-state kinds) — learned during benchmark iteration.
