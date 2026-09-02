import { useApi } from "../hooks";
import type { Incident } from "../types";

export default function Incidents() {
  const { data, loading, error } = useApi<Incident[]>("/api/incidents");

  if (loading) return <div className="loading">Loading incidents…</div>;
  if (error) return <div className="error-box">{error}</div>;
  if (!data || data.length === 0) return <div className="empty">No incidents recorded</div>;

  return (
    <div>
      <h1 className="page-title">Incidents</h1>
      <p className="page-sub">
        Correlated by the deterministic rule engine: related signals are grouped into a single
        incident, not one alert per error.
      </p>
      <div className="card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Confidence</th>
              <th>Category</th>
              <th>Detected</th>
              <th>Affected services</th>
            </tr>
          </thead>
          <tbody>
            {data.map((inc) => (
              <tr key={inc.id}>
                <td>
                  <a className="mono" href={`#/incidents/${inc.id}`} style={{ color: "var(--accent)" }}>
                    {inc.id}
                  </a>
                </td>
                <td>{inc.title}</td>
                <td>
                  <span className={`badge ${inc.severity}`}>{inc.severity}</span>
                </td>
                <td>
                  <span className={`badge ${inc.status}`}>{inc.status}</span>
                </td>
                <td className="mono">{inc.confidence.toFixed(2)}</td>
                <td className="mono dim">{inc.category}</td>
                <td className="mono dim">{new Date(inc.detected_at).toLocaleTimeString()}</td>
                <td className="dim" style={{ fontSize: 12.5 }}>
                  {inc.affected_services.join(", ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
