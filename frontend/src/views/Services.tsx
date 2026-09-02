import { useApi } from "../hooks";
import type { ServiceInfo } from "../types";

export default function Services() {
  const { data, loading, error } = useApi<ServiceInfo[]>("/api/services");

  if (loading) return <div className="loading">Loading services…</div>;
  if (error) return <div className="error-box">{error}</div>;
  if (!data || data.length === 0) return <div className="empty">No services registered</div>;

  return (
    <div>
      <h1 className="page-title">Services</h1>
      <p className="page-sub">Synthetic environment: {data.length} services and dependencies</p>
      <div className="card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <th>Service</th>
              <th>Kind</th>
              <th>Error rate</th>
              <th>Dependencies</th>
              <th>Dependents</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {data.map((svc) => {
              const err = svc.error_rate;
              const color = err === null ? "var(--text-faint)" : err > 5 ? "var(--red)" : err > 1 ? "var(--yellow)" : "var(--green)";
              return (
                <tr key={svc.name}>
                  <td className="mono">{svc.name}</td>
                  <td><span className="badge neutral">{svc.kind}</span></td>
                  <td className="mono" style={{ color }}>{err !== null ? `${err.toFixed(2)}%` : "—"}</td>
                  <td className="dim mono" style={{ fontSize: 12 }}>{svc.dependencies.join(", ") || "—"}</td>
                  <td className="dim mono" style={{ fontSize: 12 }}>{svc.dependents.join(", ") || "—"}</td>
                  <td className="dim" style={{ fontSize: 12.5, maxWidth: 260 }}>{svc.description}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
