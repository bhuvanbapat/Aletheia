# Changelog

All notable changes to SentinelOps. Format: Keep a Changelog, semantic-ish versioning.

## [0.1.0] — 2026-09-02

### Added
- Synthetic production environment: 10-service e-commerce topology, seeded
  telemetry generator (healthy baselines + causal incident windows), 5
  incident scenarios with declared ground truth.
- Telemetry ingestion: normalization, dedup, malformed-entry resilience,
  secret redaction, prompt-injection quarantine.
- Metrics engine: rolling baselines, interpretable anomaly detection
  (Iglewicz-Hoaglin modified z-score, median/MAD).
- Deterministic correlation rule engine: DB exhaustion, deployment
  regression, resource saturation, cache failure, dependency timeout;
  incident-level dedup prevents alert storms.
- Service topology engine: impact radius, propagation paths.
- AI investigator: typed 12-tool registry, evidence-first loop, hypothesis
  ranking with causal-kind priors, provider abstraction (OpenAI-compatible
  or deterministic mock), full agent-run + tool-call tracing, loop safety.
- Controlled remediation: whitelisted simulation-only actions, approval
  gate (default `approval_required`), recorded initiators/results.
- Recovery verification: measured gap-closure vs baseline; owns the
  `resolved` transition.
- Postmortem generator (rule-based, from stored records only).
- Evaluation harness: 5 isolated benchmark scenarios, scored end-to-end.
- React + TypeScript dashboard: Overview, Incidents (+ detail with
  timeline/evidence/hypotheses/remediation/trace), Services, Topology,
  Logs, Metrics, Deployments, AI Investigator, Postmortems, Evaluations,
  Settings.
- Docker packaging + GitHub Actions CI (backend tests/lint/container
  smoke; frontend typecheck/build).
- Documentation: architecture, security threat model, evaluation
  methodology, demo guide, incident data model, AI investigation design,
  8 ADRs, resume notes, interview guide.

### Fixed during development (visible via benchmark)
- Evidence-collection indentation bug (only last metric per service was
  recorded).
- Baseline pollution: mean/stddev z-score replaced with robust median/MAD.
- Remediation action matched against prompt boilerplate instead of the
  hypothesis data block.
- Symptom-over-cause hypothesis ranking (added causal-kind + state-metric
  deployment-link rules).
- Trailing-comma tuple bug in ResourceSaturationRule.name.
