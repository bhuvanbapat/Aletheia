import { useState } from "react";
import { useApi } from "../hooks";
import type { TelemetryEvent } from "../types";

const SEVERITIES = ["", "DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"];

export default function Logs() {
  const [service, setService] = useState("");
  const [severity, setSeverity] = useState("");
  const [search, setSearch] = useState("");
  const [minutes, setMinutes] = useState(120);
  const [expanded, setExpanded] = useState<string | null>(null);

  const services = useApi<{ name: string }[]>("/api/services");
  const qs = new URLSearchParams();
  if (service) qs.set("service", service);
  if (severity) qs.set("severity", severity);
  if (search) qs.set("search", search);
  qs.set("minutes", String(minutes));
  qs.set("limit", "200");
  const { data, loading, error } = useApi<{ total: number; items: TelemetryEvent[] }>(
    `/api/logs?${qs.toString()}`,
    [service, severity, search, minutes],
  );

  const sevColor = (s: string) =>
    s === "ERROR" || s === "CRITICAL"
      ? "var(--red)"
      : s === "WARN"
        ? "var(--yellow)"
        : "var(--text-dim)";

  return (
    <div>
      <h1 className="page-title">Log Explorer</h1>
      <p className="page-sub">Structured telemetry events · untrusted content is displayed as data only</p>

      <div className="toolbar">
        <select className="control" value={service} onChange={(e) => setService(e.target.value)}>
          <option value="">All services</option>
          {services.data?.map((s) => (
            <option key={s.name} value={s.name}>{s.name}</option>
          ))}
        </select>
        <select className="control" value={severity} onChange={(e) => setSeverity(e.target.value)}>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>{s || "All severities"}</option>
          ))}
        </select>
        <input
          className="control"
          placeholder="search message…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 220 }}
        />
        <select className="control" value={minutes} onChange={(e) => setMinutes(Number(e.target.value))}>
          <option value={30}>last 30 min</option>
          <option value={60}>last 60 min</option>
          <option value={120}>last 2 h</option>
          <option value={360}>last 6 h</option>
        </select>
      </div>

      {loading && <div className="loading">Querying logs…</div>}
      {error && <div className="error-box">{error}</div>}
      {data && data.items.length === 0 && (
        <div className="empty">No log events match the current filters</div>
      )}
      {data && data.items.length > 0 && (
        <div className="card" style={{ padding: 0 }}>
          <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border)" }} className="dim">
            {data.total} events
          </div>
          <table className="data">
            <thead>
              <tr>
                <th>Time</th>
                <th>Severity</th>
                <th>Service</th>
                <th>Event type</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((e) => (
                <tr key={e.id} style={{ cursor: "pointer" }} onClick={() => setExpanded(expanded === e.id ? null : e.id)}>
                  <td className="mono dim" style={{ whiteSpace: "nowrap" }}>
                    {new Date(e.timestamp).toLocaleTimeString()}
                  </td>
                  <td style={{ color: sevColor(e.severity), fontWeight: 600 }}>{e.severity}</td>
                  <td className="mono">{e.service}</td>
                  <td className="mono dim">{e.event_type}</td>
                  <td>
                    {e.message}
                    {expanded === e.id && (
                      <pre style={{
                        marginTop: 8, background: "var(--bg-raised)", padding: 10,
                        borderRadius: 6, fontSize: 12, fontFamily: "var(--mono)", overflowX: "auto",
                      }}>
                        {JSON.stringify({ metadata: e.metadata, trace_id: e.trace_id, source: e.raw_source }, null, 2)}
                      </pre>
                    )}
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
