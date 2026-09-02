import { useState } from "react";
import { useApi } from "../hooks";
import { apiPost } from "../api/client";
import type {
  AgentRun, EvidenceItem, Hypothesis, Incident, InvestigationResult,
  Postmortem, Remediation, TimelineEntry, ToolCallEntry, Verification,
} from "../types";

export default function IncidentDetail({ incidentId }: { incidentId: string }) {
  const incident = useApi<Incident>(`/api/incidents/${incidentId}`);
  const timeline = useApi<TimelineEntry[]>(`/api/incidents/${incidentId}/timeline`);
  const evidence = useApi<EvidenceItem[]>(`/api/incidents/${incidentId}/evidence`);
  const hypotheses = useApi<Hypothesis[]>(`/api/incidents/${incidentId}/hypotheses`);
  const remediations = useApi<Remediation[]>(`/api/incidents/${incidentId}/remediations`);
  const verifications = useApi<Verification[]>(`/api/incidents/${incidentId}/verifications`);
  const runs = useApi<AgentRun[]>(`/api/agent/runs?incident_id=${incidentId}`);

  const [investigating, setInvestigating] = useState(false);
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [postmortem, setPostmortem] = useState<Postmortem | null>(null);

  if (incident.loading) return <div className="loading">Loading incident…</div>;
  if (incident.error) return <div className="error-box">{incident.error}</div>;
  const inc = incident.data;
  if (!inc) return <div className="empty">Incident not found</div>;

  const runInvestigate = async () => {
    setInvestigating(true);
    try {
      const result = await apiPost<InvestigationResult>(`/api/incidents/${incidentId}/investigate`);
      setInvestigation(result);
      timeline.refresh();
      evidence.refresh();
      hypotheses.refresh();
      remediations.refresh();
      runs.refresh();
      incident.refresh();
    } finally {
      setInvestigating(false);
    }
  };

  const approve = async (rem: Remediation, approved: boolean) => {
    setBusy(rem.id);
    try {
      await apiPost(`/api/remediations/${rem.id}/approve`, { approved, approver: "human-operator" });
      remediations.refresh();
    } finally {
      setBusy(null);
    }
  };

  const execute = async (rem: Remediation) => {
    setBusy(rem.id);
    try {
      await apiPost(`/api/remediations/${rem.id}/execute`);
      remediations.refresh();
      incident.refresh();
    } finally {
      setBusy(null);
    }
  };

  const verify = async () => {
    setBusy("verify");
    try {
      await apiPost(`/api/incidents/${incidentId}/verify`);
      verifications.refresh();
      incident.refresh();
    } finally {
      setBusy(null);
    }
  };

  const generatePostmortem = async () => {
    setBusy("pm");
    try {
      const pm = await apiPost<Postmortem>(`/api/incidents/${incidentId}/postmortem`);
      setPostmortem(pm);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      {/* ---------- header ---------- */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 className="page-title" style={{ margin: 0 }}>{inc.title}</h1>
        <span className={`badge ${inc.severity}`}>{inc.severity}</span>
        <span className={`badge ${inc.status}`}>{inc.status}</span>
      </div>
      <p className="page-sub mono">
        {inc.id} · started {new Date(inc.started_at).toLocaleString()} · detected{" "}
        {new Date(inc.detected_at).toLocaleString()} · correlation confidence {inc.confidence.toFixed(2)}
      </p>
      <div className="card" style={{ padding: 12 }}>
        <b>Affected services:</b> {inc.affected_services.join(", ")}
      </div>

      {/* ---------- AI investigation ---------- */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>AI Investigation</h3>
          <button className="btn primary" onClick={runInvestigate} disabled={investigating}>
            {investigating ? "Investigating…" : "Run investigation"}
          </button>
        </div>
        {investigating && <div className="empty" style={{ marginTop: 12 }}>Agent is collecting evidence…</div>}
        {investigation && (
          <div style={{ marginTop: 14 }}>
            <div className="dim" style={{ marginBottom: 10, fontSize: 13 }}>
              Run <span className="mono">{investigation.run_id}</span> · {investigation.llm_request_count} LLM
              requests · {investigation.input_tokens + investigation.output_tokens} tokens (est.) ·{" "}
              {investigation.tool_calls.length} tool calls ·{" "}
              {investigation.demo_mode && (
                <span className="mode-pill" style={{ marginRight: 6 }}>DEMO MODE</span>
              )}
              deterministic mock provider
            </div>

            <div className="section-label">Most likely root cause</div>
            <div className="hypothesis-card top">
              <div className="hyp-header">
                <div>
                  <div className="hyp-statement">{investigation.root_cause}</div>
                  <div className="dim" style={{ fontSize: 12, marginTop: 4 }}>
                    engineering-estimated confidence
                  </div>
                </div>
                <div className="hyp-conf hyp-conf-top">
                  {(investigation.root_cause_confidence * 100).toFixed(0)}%
                </div>
              </div>
            </div>

            {investigation.hypotheses.length > 1 && (
              <>
                <div className="section-label">Alternative hypotheses considered</div>
                {investigation.hypotheses.slice(1).map((h, i) => (
                  <div className="hypothesis-card" key={i}>
                    <div className="hyp-header">
                      <div className="hyp-statement">{h.statement}</div>
                      <div className="hyp-conf">{(Math.min(h.confidence, 0.99) * 100).toFixed(0)}%</div>
                    </div>
                    {h.evidence_for?.length > 0 && (
                      <div style={{ marginTop: 8 }}>
                        {h.evidence_for.map((e, j) => (
                          <div className="evidence-item" key={j} style={{ fontSize: 12.5 }}>{e}</div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        )}
        {!investigation && !investigating && hypotheses.data && hypotheses.data.length > 0 && (
          <div>
            <div className="section-label">Stored hypotheses (last investigation)</div>
            {hypotheses.data!.map((h) => (
              <div className={`hypothesis-card${h.rank === 0 ? " top" : ""}`} key={h.id}>
                <div className="hyp-header">
                  <div className="hyp-statement">{h.statement}</div>
                  <div className="hyp-conf">{(h.confidence * 100).toFixed(0)}%</div>
                </div>
                {h.evidence_for.map((e, i) => (
                  <div className="evidence-item" key={i} style={{ fontSize: 12.5 }}>{e}</div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ---------- remediation ---------- */}
      <div className="card">
        <h3>Remediation · approval required by default</h3>
        {(!remediations.data || remediations.data.length === 0) && (
          <div className="empty">No remediation proposed yet — run an investigation first.</div>
        )}
        {remediations.data?.map((rem) => (
          <div className="hypothesis-card" key={rem.id}>
            <div className="hyp-header">
              <div>
                <div className="hyp-statement mono">{rem.action}{rem.target_service ? ` → ${rem.target_service}` : ""}</div>
                <div className="dim" style={{ fontSize: 12.5, marginTop: 4 }}>{rem.reason}</div>
                {rem.expected_effect && (
                  <div className="dim" style={{ fontSize: 12.5 }}>Expected: {rem.expected_effect}</div>
                )}
              </div>
              <div style={{ textAlign: "right" }}>
                <div className={`badge ${rem.status}`}>{rem.status}</div>
                <div style={{ marginTop: 6 }}>
                  <span className={`badge ${rem.approval_state}`}>{rem.approval_state}</span>
                </div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              {rem.approval_state === "pending" && (
                <>
                  <button
                    className="btn success small"
                    disabled={busy === rem.id}
                    onClick={() => approve(rem, true)}
                  >
                    Approve
                  </button>
                  <button
                    className="btn danger small"
                    disabled={busy === rem.id}
                    onClick={() => approve(rem, false)}
                  >
                    Reject
                  </button>
                </>
              )}
              {rem.approval_state === "approved" && rem.status !== "executed" && (
                <button className="btn primary small" disabled={busy === rem.id} onClick={() => execute(rem)}>
                  Execute (simulated)
                </button>
              )}
              {rem.executed_at && (
                <span className="dim" style={{ fontSize: 12 }}>
                  executed {new Date(rem.executed_at).toLocaleTimeString()} — {rem.result}
                </span>
              )}
            </div>
          </div>
        ))}
        <div style={{ marginTop: 10 }}>
          <button className="btn" onClick={verify} disabled={busy === "verify"}>
            {busy === "verify" ? "Measuring…" : "Verify recovery"}
          </button>
        </div>
      </div>

      {/* ---------- verification ---------- */}
      {verifications.data && verifications.data.length > 0 && (
        <div className="card">
          <h3>Recovery verification (measured, not claimed)</h3>
          {verifications.data!.map((v) => (
            <div key={v.id} style={{ marginBottom: 16 }}>
              <span className={`badge ${v.outcome}`}>{v.outcome.replace("_", " ")}</span>
              <div style={{ marginTop: 8 }}>
                {v.evidence.map((e, i) => (
                  <div className="evidence-item" key={i}>{e}</div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ---------- timeline ---------- */}
      <div className="card">
        <h3>Incident timeline</h3>
        {(!timeline.data || timeline.data.length === 0) && <div className="empty">No timeline yet</div>}
        <div className="timeline">
          {timeline.data?.map((t, i) => (
            <div className={`timeline-entry t-${t.kind}`} key={i}>
              <div className="timeline-ts">{new Date(t.timestamp).toLocaleTimeString()}</div>
              <div className="timeline-label">{t.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ---------- evidence ---------- */}
      <div className="card">
        <h3>Evidence ({evidence.data?.length ?? 0})</h3>
        {(!evidence.data || evidence.data.length === 0) && <div className="empty">No evidence collected yet</div>}
        {evidence.data?.map((e) => (
          <div className="evidence-item" key={e.id}>
            <span className="ev-kind">{e.kind} · {e.source_ref}</span>
            {e.description}
          </div>
        ))}
      </div>

      {/* ---------- agent trace ---------- */}
      {runs.data && runs.data.length > 0 && (
        <div className="card">
          <h3>Agent runs</h3>
          {runs.data!.map((r) => (
            <AgentTrace key={r.id} runId={r.id} run={r} />
          ))}
        </div>
      )}

      {/* ---------- postmortem ---------- */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>Postmortem</h3>
          <button className="btn" onClick={generatePostmortem} disabled={busy === "pm"}>
            {busy === "pm" ? "Generating…" : "Generate postmortem"}
          </button>
        </div>
        {postmortem && (
          <div style={{ marginTop: 12 }}>
            <div className="dim" style={{ fontSize: 12, marginBottom: 8 }}>
              Generated by {postmortem.generated_by} ·{" "}
              <button
                className="btn small"
                onClick={() => navigator.clipboard?.writeText(postmortem.content_markdown)}
              >
                Copy markdown
              </button>
            </div>
            <pre style={{
              whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 13,
              background: "var(--bg-raised)", padding: 16, borderRadius: 8, maxHeight: 500, overflow: "auto",
            }}>
              {postmortem.content_markdown}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

function AgentTrace({ runId, run }: { runId: string; run: AgentRun }) {
  const trace = useApi<ToolCallEntry[]>(`/api/agent/runs/${runId}/trace`);
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginBottom: 12, border: "1px solid var(--border)", borderRadius: 8, padding: 12 }}>
      <div
        style={{ display: "flex", gap: 10, alignItems: "center", cursor: "pointer" }}
        onClick={() => setOpen(!open)}
      >
        <span className="mono">{runId}</span>
        <span className={`badge ${run.status === "completed" ? "ok" : "error"}`}>{run.status}</span>
        <span className="dim" style={{ fontSize: 12.5 }}>
          {run.provider}/{run.model} · {run.llm_request_count} LLM calls · ~{run.input_tokens + run.output_tokens} tokens
        </span>
        <span className="dim" style={{ fontSize: 12, marginLeft: "auto" }}>
          {open ? "hide trace" : `show trace (${trace.data?.length ?? "?"} tool calls)`}
        </span>
      </div>
      {open && (
        <table className="data" style={{ marginTop: 10 }}>
          <thead>
            <tr>
              <th>#</th>
              <th>Tool</th>
              <th>Duration</th>
              <th>Status</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {trace.data?.map((t) => (
              <tr key={t.seq}>
                <td className="mono dim">{t.seq}</td>
                <td className="mono">{t.tool}</td>
                <td className="mono dim">{t.duration_ms.toFixed(1)} ms</td>
                <td>
                  <span className={`badge ${t.status === "ok" ? "ok" : "error"}`}>{t.status}</span>
                </td>
                <td className="dim mono" style={{ fontSize: 11.5, maxWidth: 420, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {t.error ? t.error : t.result_summary}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
