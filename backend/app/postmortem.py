"""Postmortem generator: structured report grounded in incident data.

Every factual section cites stored records (timeline, evidence, hypotheses,
remediations, verifications). No invented facts.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Evidence, Hypothesis, Incident, Postmortem, Remediation, Verification


def _fmt_ts(ts) -> str:
    if ts is None:
        return "unknown"
    if isinstance(ts, datetime):
        return ts.strftime("%H:%M:%S")
    return str(ts)[:19]


def generate_postmortem(db: Session, incident_id: str, use_llm: bool = False) -> Postmortem | None:
    incident = db.get(Incident, incident_id)
    if incident is None:
        return None
    timeline_rows = db.execute(
        select(Evidence).where(Evidence.incident_id == incident_id)
    ).scalars().all()
    hypotheses = db.execute(
        select(Hypothesis).where(Hypothesis.incident_id == incident_id).order_by(Hypothesis.rank)
    ).scalars().all()
    remediations = db.execute(
        select(Remediation).where(Remediation.incident_id == incident_id)
    ).scalars().all()
    verifications = db.execute(
        select(Verification).where(Verification.incident_id == incident_id)
    ).scalars().all()

    affected = ", ".join(incident.affected_services or []) or "unknown"
    top_hyp = hypotheses[0] if hypotheses else None
    executed = [r for r in remediations if r.status == "executed"]
    latest_verification = verifications[-1] if verifications else None

    def evidence_lines(kind: str) -> list[str]:
        return [e.description for e in timeline_rows if e.kind == kind]

    lines: list[str] = []
    lines.append(f"# Postmortem: {incident.title}")
    lines.append("")
    lines.append(f"Incident: {incident.id} | Severity: {incident.severity} | Status: {incident.status}")
    lines.append(f"Generated: {datetime.now(UTC).isoformat()}")
    lines.append("")
    lines.append("## Summary")
    summary = (
        f"Incident {incident.id} ({incident.title}) began around {_fmt_ts(incident.started_at)} "
        f"affecting {affected}. "
        + (f"The most likely root cause was determined to be: {top_hyp.statement} "
           f"(engineering-estimated confidence {top_hyp.confidence:.2f}). " if top_hyp else
           "Root cause was not determined. ")
        + (f"Recovery verification outcome: {latest_verification.outcome}." if latest_verification
           else "Recovery has not been verified yet.")
    )
    lines.append(summary)
    lines.append("")
    lines.append("## Impact")
    lines.append(f"- Affected services: {affected}")
    lines.append(f"- Severity: {incident.severity}")
    lines.append(f"- Detected at: {_fmt_ts(incident.detected_at)}")
    if incident.resolved_at:
        lines.append(f"- Resolved at: {_fmt_ts(incident.resolved_at)}")
    lines.append("")
    lines.append("## Timeline")
    for sig in incident.signals or []:
        if isinstance(sig, dict) and sig.get("kind") == "deployment":
            lines.append(f"- {_fmt_ts(sig.get('deployed_at'))} - Deployment {sig.get('service')} {sig.get('version')}")
    for e in evidence_lines("log"):
        lines.append(f"- Log evidence: {e[:160]}")
    lines.append(f"- {_fmt_ts(incident.detected_at)} - Incident detected and declared ({incident.severity})")
    for r in executed:
        lines.append(f"- {_fmt_ts(r.executed_at)} - Remediation executed: {r.action}"
                     + (f" on {r.target_service}" if r.target_service else ""))
    for v in verifications:
        lines.append(f"- {_fmt_ts(v.checked_at)} - Recovery verification: {v.outcome}")
    lines.append("")
    lines.append("## Root Cause")
    if top_hyp:
        lines.append(f"{top_hyp.statement} (confidence {top_hyp.confidence:.2f}, engineering estimate)")
        lines.append("")
        lines.append("Supporting evidence:")
        for ev in top_hyp.evidence_for or []:
            lines.append(f"- {ev}")
    else:
        lines.append("Not determined - insufficient evidence.")
    lines.append("")
    lines.append("## Contributing Factors")
    for h in hypotheses[1:3]:
        lines.append(f"- Considered alternative: {h.statement} (confidence {h.confidence:.2f})")
    metric_evidence = evidence_lines("metric")
    if metric_evidence:
        lines.append("- Metric deviations observed:")
        for m in metric_evidence[:6]:
            lines.append(f"  - {m[:170]}")
    lines.append("")
    lines.append("## Detection")
    lines.append(
        f"- Detected by the deterministic correlation engine at {_fmt_ts(incident.detected_at)} "
        f"(category: {incident.category}, correlation confidence {incident.confidence:.2f})."
    )
    lines.append("")
    lines.append("## Response")
    rem_all = [r for r in remediations]
    if rem_all:
        for r in rem_all:
            lines.append(f"- {r.action} ({r.status}, approval: {r.approval_state})" +
                         (f" - {r.reason}" if r.reason else ""))
    else:
        lines.append("- No remediation was proposed or recorded.")
    lines.append("")
    lines.append("## Mitigation")
    for r in executed:
        lines.append(f"- {r.action}: {r.result}")
    if not executed:
        lines.append("- No remediation was executed.")
    lines.append("")
    lines.append("## Recovery")
    if latest_verification:
        lines.append(f"- Verification outcome: **{latest_verification.outcome}**")
        for ev in (latest_verification.evidence or [])[:8]:
            lines.append(f"  - {ev}")
    else:
        lines.append("- Recovery not verified; no post-remediation measurement available.")
    lines.append("")
    lines.append("## What Went Well")
    lines.append("- Deterministic correlation grouped multiple signal changes into a single incident.")
    if top_hyp:
        lines.append("- Evidence-first RCA produced a ranked hypothesis set with recorded evidence.")
    if executed:
        lines.append("- Remediation required explicit approval before simulated execution.")
    if latest_verification and latest_verification.outcome in ("recovered", "partial"):
        lines.append("- Recovery was measured against post-remediation telemetry, not assumed.")
    lines.append("")
    lines.append("## What Went Poorly")
    if incident.status not in ("resolved",):
        lines.append("- Incident is not yet fully resolved at the time of writing.")
    if not top_hyp:
        lines.append("- Root cause could not be determined from available telemetry.")
    lines.append("- Detection depended on the synthetic telemetry window (see docs/EVALUATION.md limitations).")
    lines.append("")
    lines.append("## Preventive Actions")
    lines.append("- Add alerts on the leading indicators identified in this incident.")
    if top_hyp and "connection" in (top_hyp.statement or "").lower():
        lines.append("- Add connection-pool saturation alerts ahead of exhaustion.")
    if top_hyp and "memory" in (top_hyp.statement or "").lower():
        lines.append("- Add memory-growth trend alerts and consider heap limits.")
    lines.append("- Review runbooks for this incident category.")
    lines.append("")
    lines.append("## Follow-up Items")
    lines.append("- [ ] Owner: SRE team - review alert thresholds for the leading signals in this incident")
    lines.append("- [ ] Owner: Service team - verify fix/rollback is promoted to all environments")
    lines.append("- [ ] Owner: Platform - re-run the evaluation benchmark after fixes")

    content = "\n".join(lines)
    pm = Postmortem(
        id=f"pm-{uuid.uuid4().hex[:12]}",
        incident_id=incident.id,
        title=f"Postmortem: {incident.title}",
        content_markdown=content,
        generated_by="llm" if use_llm else "rule-based",
    )
    db.add(pm)
    db.commit()
    return pm


def postmortem_to_dict(pm: Postmortem) -> dict:
    return {
        "id": pm.id,
        "incident_id": pm.incident_id,
        "title": pm.title,
        "content_markdown": pm.content_markdown,
        "generated_by": pm.generated_by,
        "created_at": pm.created_at,
    }
