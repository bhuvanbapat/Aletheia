# ADR-007: Evidence-first root-cause analysis

**Status:** Accepted

## Context
RCA systems that print confident conclusions without verifiable support
are worse than useless in an incident.

## Decision
Every hypothesis stores `evidence_for`/`evidence_against` gathered by the
agent's tool calls; every incident keeps an Evidence table (metric rows
with current-vs-baseline numbers, redacted log rows, analysis rows from
the correlation engine); the postmortem generator may only reference
stored records; the verification engine may only claim recovery from
measured post-remediation telemetry.

## Consequences
- The UI can always answer "what evidence supports this?" with links to
  collected data.
- Fabrication is structurally hard: conclusions without evidence rows
  cannot be rendered as fact.
- The concept of OBSERVED FACT / INFERENCE / HYPOTHESIS /
  RECOMMENDATION / EXECUTED ACTION / VERIFIED RESULT is legible
  throughout the pipeline and UI.
