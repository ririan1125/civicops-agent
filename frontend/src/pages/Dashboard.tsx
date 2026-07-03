import React from "react";
import { Database } from "lucide-react";
import { api } from "../api";
import { Bars } from "../components/Bars";
import { Metric } from "../components/Metric";
import type { DashboardSummary } from "../types";

export function Dashboard() {
  const [summary, setSummary] = React.useState<DashboardSummary | null>(null);
  const [limit, setLimit] = React.useState(1000);
  const [status, setStatus] = React.useState("");

  const load = React.useCallback(async () => {
    setSummary(await api<DashboardSummary>("/dashboard/summary"));
  }, []);

  React.useEffect(() => {
    load().catch((error: Error) => setStatus(error.message));
  }, [load]);

  async function ingest() {
    setStatus("Importing NYC 311 records...");
    const result = await api<{ fetched_count: number; inserted_count: number; updated_count: number; status: string }>("/ingestion/run", {
      method: "POST",
      body: JSON.stringify({ limit })
    });
    setStatus(`Ingestion ${result.status}: fetched ${result.fetched_count}, inserted ${result.inserted_count}, updated ${result.updated_count}.`);
    await load();
  }

  return (
    <main className="workspace">
      <section className="hero-band">
        <div>
          <h1>CivicOps Agent</h1>
          <p>Urban service request analytics, tool-planned SQL, hybrid RAG, and traceable operations workflow.</p>
        </div>
        <div className="ingest-box">
          <label htmlFor="limit">NYC 311 import limit</label>
          <input id="limit" type="number" min={1} max={10000} value={limit} onChange={(event) => setLimit(Number(event.target.value))} />
          <button onClick={ingest}>
            <Database size={16} /> Import data
          </button>
        </div>
      </section>

      {status ? <div className="status">{status}</div> : null}

      <section className="metric-grid">
        <Metric label="Total requests" value={summary?.total_requests ?? 0} />
        <Metric label="Open requests" value={summary?.open_requests ?? 0} />
        <Metric label="Closed requests" value={summary?.closed_requests ?? 0} />
        <Metric label="Avg resolution" value={summary?.average_resolution_hours ? `${summary.average_resolution_hours}h` : "n/a"} />
      </section>

      <div className="grid-two">
        <Bars title="Top complaint types" items={summary?.top_complaints ?? []} />
        <Bars title="Borough distribution" items={summary?.borough_distribution ?? []} />
        <Bars title="Agency workload" items={summary?.agency_workload ?? []} />
        <Bars title="Daily trend" items={summary?.daily_trend ?? []} />
      </div>
    </main>
  );
}
