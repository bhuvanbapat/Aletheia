# ADR-006: Controlled remediation

**Status:** Accepted

## Context
An AI system that suggests actions must never silently take them —
especially not against a host or real infrastructure.

## Decision
1. Whitelisted verbs only: rollback_deployment, restart_service,
   scale_service, clear_cache, increase_connection_pool,
   disable_feature_flag. There is no subprocess/host-execution code path
   anywhere in the backend.
2. Mode matrix (`remediation_mode`): analysis | recommend |
   approval_required (**default**) | simulation | execute.
3. Approval is an explicit recorded state (`pending → approved/rejected`,
   with approver identity).
4. Actions act only on the synthetic environment: executing generates
   recovery telemetry in the simulation and records initiator, reason,
   params, expected effect, result.

## Consequences
- The approval gate is enforced server-side and verified by tests
  (execution without approval returns `blocked`).
- Demo flows show the whole safety story: blocked → approve → execute →
  measure.
- Real infrastructure connectors would need their own mode, whitelist,
  and audit surface — deliberately out of scope.
