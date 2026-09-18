import { NavLink, Outlet, useRouteError } from "react-router-dom";

export function AppShell() {
  return (
    <div className="app-shell">
      <TopBar />
      <div className="layout">
        <Sidebar />
        <main className="main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

import { useHealth } from "./hooks";

function TopBar() {
  const { data, loading, error } = useHealth();
  return (
    <header className="topbar">
      <a className="brand" href="#/overview">
        <span className="brand-dot" /> Aletheia
      </a>
      <span className="spacer" />
      {loading && <span className="top-stat">connecting…</span>}
      {error && <span className="top-stat" style={{ color: "var(--red)" }}>API offline</span>}
      {data && (
        <>
          <span className="top-stat">
            env <b>{data.environment}</b>
          </span>
          <span className="top-stat">
            status{" "}
            <b style={{ color: data.status === "ok" ? "var(--green)" : "var(--red)" }}>{data.status}</b>
          </span>
          <span className={`mode-pill ${data.synthetic === false ? "live" : ""}`}>
            {data.synthetic ? "SYNTHETIC DEMO" : "LIVE"}
          </span>
        </>
      )}
    </header>
  );
}

const NAV = [
  { to: "/overview", label: "Overview", icon: "▤" },
  { to: "/incidents", label: "Incidents", icon: "⚑" },
  { to: "/services", label: "Services", icon: "☁" },
  { to: "/topology", label: "Topology", icon: "⌗" },
  { to: "/logs", label: "Logs", icon: "☰" },
  { to: "/metrics", label: "Metrics", icon: "∿" },
  { to: "/deployments", label: "Deployments", icon: "↑" },
  { to: "/investigator", label: "AI Investigator", icon: "◎" },
  { to: "/postmortems", label: "Postmortems", icon: "✎" },
  { to: "/evaluations", label: "Evaluations", icon: "✓" },
  { to: "/settings", label: "Settings", icon: "⚙" },
];

function Sidebar() {
  return (
    <nav className="sidebar">
      {NAV.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
        >
          <span className="nav-icon">{item.icon}</span>
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

export function ErrorBoundary() {
  const error = useRouteError();
  return (
    <div>
      <h1 className="page-title">Something went wrong</h1>
      <div className="error-box">{String(error)}</div>
    </div>
  );
}

