import type { BreakdownItem } from "../types";

export function Bars({ title, items }: { title: string; items: BreakdownItem[] }) {
  const max = Math.max(1, ...items.map((item) => item.value));
  return (
    <section className="panel">
      <h2>{title}</h2>
      <div className="bars">
        {items.length === 0 ? <p className="empty">No data yet. Run ingestion first.</p> : null}
        {items.map((item) => (
          <div className="bar-row" key={item.label}>
            <span>{item.label || "Unknown"}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${Math.max(4, (item.value / max) * 100)}%` }} />
            </div>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}
