import React from "react";
import { Activity } from "lucide-react";
import { api } from "../api";
import type { TraceRecord } from "../types";

export function Traces() {
  const [traces, setTraces] = React.useState<TraceRecord[]>([]);

  async function load() {
    setTraces(await api<TraceRecord[]>("/traces"));
  }

  React.useEffect(() => {
    load().catch(() => undefined);
  }, []);

  return (
    <main className="workspace">
      <section className="tool-header">
        <h1>Execution Traces</h1>
        <p>Every SQL/RAG/route action is recorded for debugging, audit, and evaluation.</p>
      </section>
      <button onClick={load}>
        <Activity size={16} /> Refresh traces
      </button>
      <section className="panel">
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>ID</th><th>Route</th><th>Tool</th><th>Status</th><th>Latency</th><th>Query</th></tr>
            </thead>
            <tbody>
              {traces.map((trace) => (
                <tr key={trace.id}>
                  <td>{trace.id}</td>
                  <td>{trace.route}</td>
                  <td>{trace.selected_tool}</td>
                  <td>{trace.status}</td>
                  <td>{trace.latency_ms}ms</td>
                  <td>{trace.user_query}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
