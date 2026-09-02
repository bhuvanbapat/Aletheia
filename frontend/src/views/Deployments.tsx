import { useApi } from "../hooks";
import type { Deployment } from "../types";

export default function Deployments() {
  const { data, loading, error } = useApi<Deployment[]>("/api/deployments?hours=48");

  if (loading) return <div className="loading">Loading deployments…</div>;
  if (error) return <div className="error-box">{error}</div>;
  if (!data || data.length === 0) return <div className="empty">No deployments recorded</div>;

  return (
    <div>
      <h1 className="page-title">Deployments</h1>
      <p className="page-sub">
        Deployment events are first-class investigation evidence: temporal correlation with
        incidents often identifies regressions.
      </p>
      <div className="card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <th>Time</th>
              <th>Service</th>
              <th>Version</th>
              <th>Commit</th>
              <th>Actor</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.id}>
                <td className="mono dim" style={{ whiteSpace: "nowrap" }}>{new Date(d.timestamp).toLocaleString()}</td>
                <td className="mono">{d.service}</td>
                <td className="mono">{d.version}</td>
                <td className="mono dim">{d.commit}</td>
                <td className="dim">{d.actor}</td>
                <td className="dim">{d.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
