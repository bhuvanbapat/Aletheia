import { useApi } from "../hooks";
import type { SettingsInfo } from "../types";

interface ToolDef {
  name: string;
  description: string;
  args: Record<string, string>;
}

export default function Settings() {
  const settings = useApi<SettingsInfo>("/api/settings");
  const tools = useApi<ToolDef[]>("/api/tools");
  const stats = useApi<{ accepted_total: number; malformed_total: number; duplicates_total: number }>(
    "/api/telemetry/stats",
  );

  return (
    <div>
      <h1 className="page-title">Settings</h1>
      <p className="page-sub">Runtime configuration — all values come from the backend</p>

      <div className="grid grid-2">
        <div className="card">
          <h3>AI provider</h3>
          {settings.loading && <div className="loading">loading…</div>}
          {settings.data && (
            <table className="data">
              <tbody>
                <tr><td className="dim">Provider</td><td className="mono">{settings.data.llm_provider}</td></tr>
                <tr><td className="dim">Model</td><td className="mono">{settings.data.llm_model}</td></tr>
                <tr>
                  <td className="dim">LLM enabled</td>
                  <td><span className={`badge ${settings.data.llm_enabled ? "ok" : "neutral"}`}>{String(settings.data.llm_enabled)}</span></td>
                </tr>
                <tr>
                  <td className="dim">Mode</td>
                  <td>{settings.data.demo_mode ? "Deterministic mock (no external API)" : "OpenAI-compatible endpoint"}</td></tr>
                <tr>
                  <td className="dim">Demo mode</td>
                  <td>{settings.data.demo_mode ? "Yes — results are simulated and deterministic, clearly labeled in the UI" : "No"}</td></tr>
              </tbody>
            </table>
          )}
          <p className="dim" style={{ fontSize: 12, marginTop: 10 }}>
            Configure via environment: Aletheia_LLM_BASE_URL, Aletheia_LLM_API_KEY,
            Aletheia_LLM_MODEL. Without a key, the platform runs fully in deterministic mock mode.
          </p>
        </div>

        <div className="card">
          <h3>Remediation control</h3>
          {settings.data && (
            <table className="data">
              <tbody>
                <tr>
                  <td className="dim">Mode</td>
                  <td><span className="badge approved">{settings.data.remediation_mode}</span></td>
                </tr>
                <tr><td className="dim">Agent max tool calls</td><td className="mono">{settings.data.agent_max_tool_calls}</td></tr>
              </tbody>
            </table>
          )}
          <p className="dim" style={{ fontSize: 12, marginTop: 10 }}>
            Modes: analysis · recommend · approval_required (default) · simulation · execute.
            Remediation only ever acts against the synthetic environment — no host commands.
          </p>
        </div>
      </div>

      <div className="card">
        <h3>Ingestion health</h3>
        {stats.data && (
          <div className="grid grid-3">
            <div className="stat-card">
              <div className="stat-label">Events accepted</div>
              <div className="stat-value">{stats.data.accepted_total}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Duplicates skipped</div>
              <div className="stat-value">{stats.data.duplicates_total}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Malformed skipped</div>
              <div className="stat-value">{stats.data.malformed_total}</div>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h3>Agent tool registry</h3>
        <table className="data">
          <thead>
            <tr><th>Tool</th><th>Description</th><th>Args</th></tr>
          </thead>
          <tbody>
            {tools.data?.map((t) => (
              <tr key={t.name}>
                <td className="mono">{t.name}</td>
                <td className="dim">{t.description}</td>
                <td className="mono dim" style={{ fontSize: 11.5 }}>{JSON.stringify(t.args)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

