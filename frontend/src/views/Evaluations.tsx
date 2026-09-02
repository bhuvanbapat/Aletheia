import { useState } from "react";
import { apiPost } from "../api/client";
import { useApi } from "../hooks";
import type { EvaluationReport } from "../types";

export default function Evaluations() {
  const stored = useApi<EvaluationReport["scenarios"][number][]>("/api/evaluations");
  const [running, setRunning] = useState(false);
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runBenchmark = async () => {
    setRunning(true);
    setError(null);
    try {
      const result = await apiPost<EvaluationReport>("/api/evaluations/run");
      setReport(result);
      stored.refresh();
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <h1 className="page-title">Evaluation Benchmarks</h1>
      <p className="page-sub">
        Synthetic benchmark incidents with known ground truth. These measure the system against
        simulated scenarios — not real production incidents. See docs/EVALUATION.md.
      </p>

      <div className="card">
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button className="btn primary" onClick={runBenchmark} disabled={running}>
            {running ? "Running 5 scenarios…" : "Run benchmark suite"}
          </button>
          {running && <span className="dim">investigating → remediating → verifying each scenario</span>}
        </div>
        {error && <div className="error-box">{error}</div>}
        {report && (
          <div className="grid grid-4" style={{ marginTop: 16 }}>
            <div className="stat-card">
              <div className="stat-label">Root-cause accuracy</div>
              <div className="stat-value">{(report.aggregate.root_cause_accuracy * 100).toFixed(0)}%</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Affected services</div>
              <div className="stat-value">{(report.aggregate.affected_service_accuracy * 100).toFixed(0)}%</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Remediation</div>
              <div className="stat-value">{(report.aggregate.remediation_accuracy * 100).toFixed(0)}%</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Recovery verified</div>
              <div className="stat-value">{(report.aggregate.recovery_verification_rate * 100).toFixed(0)}%</div>
            </div>
          </div>
        )}
      </div>

      {(report?.scenarios ?? stored.data ?? []).length > 0 && (
        <div className="card" style={{ padding: 0 }}>
          <table className="data">
            <thead>
              <tr>
                <th>Scenario</th>
                <th>Root cause</th>
                <th>Services</th>
                <th>Remediation</th>
                <th>Recovery</th>
                <th>Evidence</th>
                <th>Tools</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {(report?.scenarios ?? stored.data!).map((s) => (
                <tr key={s.scenario_id + (s.incident_id ?? "")}>
                  <td className="mono dim">{s.scenario_id}</td>
                  <td><span className={`badge ${s.root_cause_correct ? "ok" : "error"}`}>{s.root_cause_correct ? "correct" : "miss"}</span></td>
                  <td><span className={`badge ${s.affected_services_correct ? "ok" : "error"}`}>{s.affected_services_correct ? "correct" : "miss"}</span></td>
                  <td>
                    {s.remediation_correct === null
                      ? <span className="badge neutral">n/a</span>
                      : <span className={`badge ${s.remediation_correct ? "ok" : "error"}`}>{s.remediation_correct ? "correct" : "miss"}</span>}
                  </td>
                  <td><span className={`badge ${s.recovery_verified ? "ok" : "error"}`}>{s.recovery_verified ? "verified" : "no"}</span></td>
                  <td className="mono dim">{s.evidence_count}</td>
                  <td className="mono dim">{s.tool_calls}</td>
                  <td className="mono" style={{ fontWeight: 700 }}>{s.score?.toFixed(2) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(report?.scenarios ?? stored.data ?? []).length > 0 && (
        <div className="card">
          <h3>Predicted vs known root causes (full transparency)</h3>
          <table className="data">
            <thead>
              <tr><th>Scenario</th><th>Known root cause</th><th>Predicted</th></tr>
            </thead>
            <tbody>
              {(report?.scenarios ?? stored.data!).map((s) => (
                <tr key={"detail-" + s.scenario_id}>
                  <td className="mono dim">{s.scenario_id}</td>
                  <td className="dim" style={{ fontSize: 12.5 }}>{s.known_root_cause}</td>
                  <td style={{ fontSize: 12.5, color: s.root_cause_correct ? "var(--green)" : "var(--red)" }}>
                    {s.predicted_root_cause ?? "—"}
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
