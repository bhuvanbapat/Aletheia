import { useApi } from "../hooks";
import type { Postmortem } from "../types";

export default function Postmortems() {
  const { data, loading, error } = useApi<Postmortem[]>("/api/postmortems");

  if (loading) return <div className="loading">Loading postmortems…</div>;
  if (error) return <div className="error-box">{error}</div>;
  if (!data || data.length === 0) {
    return (
      <div>
        <h1 className="page-title">Postmortems</h1>
        <div className="empty">
          No postmortems generated yet — open an incident, complete its lifecycle, then click
          "Generate postmortem".
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="page-title">Postmortems</h1>
      <p className="page-sub">Every factual statement is grounded in stored incident data</p>
      {data.map((pm) => (
        <div className="card" key={pm.id}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
            <h3 style={{ marginBottom: 0 }}>{pm.title}</h3>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span className="dim" style={{ fontSize: 12 }}>
                {pm.incident_id} · {pm.generated_by} · {new Date(pm.created_at).toLocaleString()}
              </span>
              <button className="btn small" onClick={() => navigator.clipboard?.writeText(pm.content_markdown)}>
                Copy
              </button>
              <button
                className="btn small"
                onClick={() => {
                  const blob = new Blob([pm.content_markdown], { type: "text/markdown" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `postmortem-${pm.incident_id}.md`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                Download
              </button>
            </div>
          </div>
          <pre style={{
            whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 13, marginTop: 12,
            background: "var(--bg-raised)", padding: 16, borderRadius: 8, maxHeight: 600, overflow: "auto",
          }}>
            {pm.content_markdown}
          </pre>
        </div>
      ))}
    </div>
  );
}
