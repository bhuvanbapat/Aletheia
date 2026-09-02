import { useMemo, useState } from "react";
import {
  CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { useApi } from "../hooks";
import type { MetricSeries, ServiceInfo } from "../types";

export default function Metrics() {
  const services = useApi<ServiceInfo[]>("/api/services");
  const [service, setService] = useState("api-gateway");
  const [metric, setMetric] = useState("p95_latency_ms");

  const series = useApi<MetricSeries>(
    `/api/metrics?service=${encodeURIComponent(service)}&metric=${encodeURIComponent(metric)}&minutes=120`,
    [service, metric],
  );

  const chartData = useMemo(
    () =>
      (series.data?.series ?? []).map((p) => ({
        t: new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        value: p.value,
      })),
    [series.data],
  );

  const anomalyPoints = useMemo(() => {
    if (!series.data?.anomalies.length || chartData.length === 0) return [];
    return series.data.anomalies.map((a) => {
      const t = new Date(a.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      return { t, value: a.value, explanation: a.explanation };
    });
  }, [series.data, chartData.length]);

  const availableMetrics = useMemo(() => {
    const hints: Record<string, string[]> = {
      "api-gateway": ["p95_latency_ms", "error_rate", "request_rate"],
      "orders-db": ["db_latency_ms", "db_connections", "db_slow_queries"],
      "orders-service": ["p95_latency_ms", "error_rate", "memory_mb"],
      "payments-service": ["p95_latency_ms", "error_rate"],
      "inventory-service": ["cache_hit_rate", "p95_latency_ms"],
      "notification-service": ["queue_depth", "p95_latency_ms"],
    };
    return hints[service] ?? ["error_rate", "p95_latency_ms"];
  }, [service]);

  return (
    <div>
      <h1 className="page-title">Metric Explorer</h1>
      <p className="page-sub">
        Actual stored telemetry · anomaly markers computed by modified z-score vs rolling baseline
      </p>

      <div className="toolbar">
        <select
          className="control"
          value={service}
          onChange={(e) => {
            setService(e.target.value);
            setMetric("p95_latency_ms");
          }}
        >
          {services.data?.map((s) => (
            <option key={s.name} value={s.name}>{s.name}</option>
          ))}
        </select>
        <select className="control" value={metric} onChange={(e) => setMetric(e.target.value)}>
          {availableMetrics.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      {series.loading && <div className="loading">Loading series…</div>}
      {series.error && <div className="error-box">{series.error}</div>}
      {series.data && chartData.length === 0 && (
        <div className="empty">No data for {service}/{metric}</div>
      )}

      {series.data && chartData.length > 0 && (
        <>
          <div className="card">
            <h3>{service} / {metric}</h3>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                <XAxis dataKey="t" stroke="var(--text-faint)" fontSize={11} interval="preserveStartEnd" />
                <YAxis stroke="var(--text-faint)" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-raised)", border: "1px solid var(--border-strong)",
                    borderRadius: 6, fontSize: 12,
                  }}
                />
                <Line type="monotone" dataKey="value" stroke="var(--accent)" dot={false} strokeWidth={1.8} />
                {anomalyPoints.map((a, i) => (
                  <ReferenceDot key={i} x={a.t} y={a.value} r={5} fill="var(--red)" stroke="var(--red)" />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {series.data.anomalies.length > 0 && (
            <div className="card">
              <h3>Why this was flagged</h3>
              {series.data.anomalies.map((a, i) => (
                <div className="evidence-item" key={i}>
                  <span className="ev-kind">{a.method} · z={a.z_score}</span>
                  {a.explanation}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
