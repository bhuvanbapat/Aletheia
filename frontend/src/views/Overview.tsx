import { useApi } from "../hooks";
import type { OverviewData } from "../types";

export default function Overview() {
  const { data, loading, error } = useApi<OverviewData>("/api/overview");

  if (loading) return <div className="loading">Loading environment…</div>;
  if (error) return <div className="error-box">{error}</div>;
  if (!data) return <div className="empty">No data</div>;

  return (
    <div>
      <h1 className="page-title">Overview</h1>
      <p className="page-sub">
        Synthetic production environment · {data.service_count} services · last telemetry{" "}
        {data.latest_telemetry_time ? new Date(data.latest_telemetry_time).toLocaleTimeString() : "—"}
      </p>

      <div className="grid grid-4">
        <div className="stat-card">
          <div className="stat-label">Active incidents</div>
          <div className="stat-value" style={{ color: data.active_incident_count > 0 ? "var(--red)" : "var(--green)" }}>
            {data.active_incident_count}
          </div>
          <div className="stat-sub">{data.affected_services.length} services affected</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Gateway error rate</div>
          <div className="stat-value">
            {data.gateway.error_rate !== null ? `${data.gateway.error_rate.toFixed(2)}%` : "—"}
          </div>
          <div className="stat-sub">api-gateway, current</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Gateway p95 latency</div>
          <div className="stat-value">
            {data.gateway.p95_latency_ms !== null ? `${Math.round(data.gateway.p95_latency_ms)} ms` : "—"}
          </div>
          <div className="stat-sub">api-gateway, current</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Metric anomalies</div>
          <div className="stat-value" style={{ color: data.anomaly_count > 0 ? "var(--yellow)" : "var(--green)" }}>
            {data.anomaly_count}
          </div>
          <div className="stat-sub">detected vs 60m baseline</div>
        </div>
      </div>

      <div className="grid grid-2" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>Active incidents</h3>
          {data.active_incidents.length === 0 && <div className="empty">No active incidents</div>}
          {data.active_incidents.map((inc) => (
            <div key={inc.id} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <span className={`badge ${inc.severity}`}>{inc.severity}</span>
                <a href={`#/incidents/${inc.id}`} style={{ color: "var(--text)", fontWeight: 600, fontSize: 13.5 }}>
                  {inc.title}
                </a>
                <span className={`badge ${inc.status}`}>{inc.status}</span>
              </div>
              <div className="dim" style={{ fontSize: 12.5, marginTop: 4 }}>
                {inc.affected_services.join(", ")}
              </div>
            </div>
          ))}
        </div>

        <div className="card">
          <h3>Anomalies (last detection pass)</h3>
          {data.anomalies.length === 0 && <div className="empty">No anomalies detected</div>}
          {data.anomalies.map((a, i) => (
            <div className="evidence-item" key={i}>
              <span className="ev-kind">{a.service}/{a.metric} · z={a.z_score}</span>
              {a.explanation}
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Recent deployments</h3>
        {data.recent_deployments.length === 0 && <div className="empty">No deployments recorded</div>}
        <table className="data">
          <thead>
            <tr>
              <th>Time</th>
              <th>Service</th>
              <th>Version</th>
            </tr>
          </thead>
          <tbody>
            {data.recent_deployments.map((d, i) => (
              <tr key={i}>
                <td className="mono dim">{new Date(d.timestamp).toLocaleString()}</td>
                <td className="mono">{d.service}</td>
                <td className="mono">{d.version}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
