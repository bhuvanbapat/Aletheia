import { useMemo, useState } from "react";
import { useApi } from "../hooks";
import type { Incident, TopologyData } from "../types";

const NODE_W = 168;
const NODE_H = 40;
const COL_GAP = 260;
const ROW_GAP = 70;

export default function Topology() {
  const { data, loading, error } = useApi<TopologyData>("/api/topology");
  const incidents = useApi<Incident[]>("/api/incidents?status=open");
  const [selected, setSelected] = useState<string | null>(null);

  const layout = useMemo(() => {
    if (!data) return null;
    // layered layout: depth = longest distance from a root (no dependents)
    const dependents = new Map<string, string[]>();
    const dependencies = new Map<string, string[]>();
    for (const e of data.edges) {
      if (!dependents.has(e.target)) dependents.set(e.target, []);
      dependents.get(e.target)!.push(e.source);
      if (!dependencies.has(e.source)) dependencies.set(e.source, []);
      dependencies.get(e.source)!.push(e.target);
    }
    const depth = (node: string, seen = new Set<string>()): number => {
      if (seen.has(node)) return 0;
      seen.add(node);
      const deps = dependencies.get(node) ?? [];
      if (deps.length === 0) return 0;
      return 1 + Math.max(...deps.map((d) => depth(d, seen)));
    };
    const layers = new Map<number, string[]>();
    let maxDepth = 0;
    for (const n of data.nodes) {
      const d = depth(n.id);
      maxDepth = Math.max(maxDepth, d);
      if (!layers.has(d)) layers.set(d, []);
      layers.get(d)!.push(n.id);
    }
    const positions = new Map<string, { x: number; y: number }>();
    for (const [d, nodes] of layers) {
      nodes.forEach((id, i) => {
        positions.set(id, { x: d * COL_GAP + 20, y: i * ROW_GAP + 60 });
      });
    }
    const width = (maxDepth + 1) * COL_GAP + 60;
    const height = Math.max(...[...positions.values()].map((p) => p.y)) + 100;
    return { positions, width, height };
  }, [data]);

  if (loading) return <div className="loading">Loading topology…</div>;
  if (error) return <div className="error-box">{error}</div>;
  if (!data || !layout) return <div className="empty">No topology data</div>;

  const affected = new Set<string>();
  incidents.data?.forEach((inc) => inc.affected_services.forEach((s) => affected.add(s)));

  const selectedInfo = selected
    ? data.nodes.find((n) => n.id === selected)
    : null;
  const selectedDeps = selected
    ? data.edges.filter((e) => e.source === selected || e.target === selected)
    : [];

  return (
    <div>
      <h1 className="page-title">Service Topology</h1>
      <p className="page-sub">
        Dependency graph used during incident investigation. Red nodes are affected by active
        incidents. Click a node to inspect its relationships.
      </p>

      <div className="card" style={{ overflowX: "auto" }}>
        <svg width={layout.width} height={layout.height} className="topology-svg">
          {data.edges.map((e, i) => {
            const from = layout.positions.get(e.source);
            const to = layout.positions.get(e.target);
            if (!from || !to) return null;
            const x1 = from.x + NODE_W;
            const y1 = from.y + NODE_H / 2;
            const x2 = to.x;
            const y2 = to.y + NODE_H / 2;
            const mid = (x1 + x2) / 2;
            return (
              <path
                key={i}
                className="topo-edge"
                d={`M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`}
                strokeDasharray={e.critical ? undefined : "4 3"}
              />
            );
          })}
          {data.nodes.map((n) => {
            const pos = layout.positions.get(n.id);
            if (!pos) return null;
            const isAffected = affected.has(n.id);
            const isDb = n.kind === "database";
            const isExternal = n.kind === "external";
            return (
              <g
                key={n.id}
                className={`topo-node${isAffected ? " affected" : ""}`}
                transform={`translate(${pos.x}, ${pos.y})`}
                onClick={() => setSelected(n.id === selected ? null : n.id)}
              >
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={6}
                  fill="var(--bg-raised)"
                  stroke={selected === n.id ? "var(--accent)" : isAffected ? "var(--red)" : "var(--border-strong)"}
                  strokeWidth={selected === n.id ? 2 : 1}
                />
                <text x={12} y={25} style={{ fontWeight: 600 }}>
                  {n.id}
                </text>
                <text x={NODE_W - 12} y={25} textAnchor="end" style={{ fill: isDb ? "var(--purple)" : isExternal ? "var(--yellow)" : "var(--text-faint)", fontSize: 10 }}>
                  {n.kind}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {selectedInfo && (
        <div className="card">
          <h3>{selectedInfo.id}</h3>
          <p className="dim" style={{ fontSize: 13 }}>{selectedInfo.description}</p>
          <table className="data">
            <thead>
              <tr><th>Relationship</th><th>Other side</th></tr>
            </thead>
            <tbody>
              {selectedDeps.map((e, i) => (
                <tr key={i}>
                  <td className="dim">{e.source === selected ? `depends on (${e.type})` : `is depended on (${e.type})`}</td>
                  <td className="mono">{e.source === selected ? e.target : e.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
