import { useApi } from "../hooks";
import type { AgentRun, Incident, ToolCallEntry } from "../types";
import { useState } from "react";

export default function Investigator() {
  const incidents = useApi<Incident[]>("/api/incidents");
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const trace = useApi<ToolCallEntry[]>(selectedRun ? `/api/agent/runs/${selectedRun}/trace` : null, [selectedRun]);

  const allRuns = useApi<AgentRun[]>("/api/agent/runs");
  const activeRun = selectedRun ? allRuns.data?.find((r) => r.id === selectedRun) : null;

  return (
    <div>
      <h1 className="page-title">AI Investigator</h1>
      <p className="page-sub">
        The agent's work is fully observable: every tool call, duration, status, and token
        estimate. Telemetry content is treated as untrusted data, never instructions.
      </p>

      <div className="card">
        <h3>Incidents with investigations</h3>
        <table className="data">
          <thead>
            <tr>
              <th>Incident</th>
              <th>Title</th>
              <th>Status</th>
              <th>Root cause (last analysis)</th>
            </tr>
          </thead>
          <tbody>
            {incidents.data?.map((inc) => (
              <tr key={inc.id}>
                <td>
                  <a className="mono" href={`#/incidents/${inc.id}`} style={{ color: "var(--accent)" }}>{inc.id}</a>
                </td>
                <td>{inc.title}</td>
                <td><span className={`badge ${inc.status}`}>{inc.status}</span></td>
                <td className="dim" style={{ fontSize: 12.5 }}>{inc.root_cause ?? "not analyzed"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Agent runs</h3>
        {(!allRuns.data || allRuns.data.length === 0) && (
          <div className="empty">No investigations run yet — open an incident and click "Run investigation"</div>
        )}
        <table className="data">
          <thead>
            <tr>
              <th>Run</th>
              <th>Incident</th>
              <th>Provider</th>
              <th>LLM calls</th>
              <th>Tokens (est.)</th>
              <th>Status</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            {allRuns.data?.map((r) => (
              <tr key={r.id} style={{ cursor: "pointer" }} onClick={() => setSelectedRun(r.id === selectedRun ? null : r.id)}>
                <td className="mono">{r.id}</td>
                <td className="mono dim">{r.incident_id}</td>
                <td className="mono dim">{r.provider}/{r.model}</td>
                <td className="mono">{r.llm_request_count}</td>
                <td className="mono">{r.input_tokens + r.output_tokens}</td>
                <td><span className={`badge ${r.status === "completed" ? "ok" : "error"}`}>{r.status}</span></td>
                <td className="mono dim">{new Date(r.started_at).toLocaleTimeString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedRun && activeRun && (
        <div className="card">
          <h3>Trace · {selectedRun}</h3>
          {activeRun.stop_reason && (
            <div className="dim" style={{ marginBottom: 8, fontSize: 12.5 }}>
              stop reason: {activeRun.stop_reason}
            </div>
          )}
          {trace.loading && <div className="loading">Loading trace…</div>}
          <table className="data">
            <thead>
              <tr>
                <th>#</th>
                <th>Tool</th>
                <th>Args</th>
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
                  <td className="mono dim" style={{ fontSize: 11.5, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {JSON.stringify(t.args)}
                  </td>
                  <td className="mono dim">{t.duration_ms.toFixed(1)} ms</td>
                  <td><span className={`badge ${t.status === "ok" ? "ok" : "error"}`}>{t.status}</span></td>
                  <td className="dim mono" style={{ fontSize: 11.5, maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {t.error || t.result_summary}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
