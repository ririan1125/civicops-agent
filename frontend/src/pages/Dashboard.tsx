import React from "react";
import { Database, RefreshCcw } from "lucide-react";
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

  async function syncLatest() {
    setStatus("Syncing latest NYC 311 records...");
    const result = await api<{
      fetched_count: number;
      inserted_count: number;
      updated_count: number;
      status: string;
      sync_start_date: string | null;
    }>("/ingestion/sync-latest", {
      method: "POST",
      body: JSON.stringify({ limit: 5000, lookback_days: 7 })
    });
    setStatus(
      `Latest sync ${result.status}: fetched ${result.fetched_count}, inserted ${result.inserted_count}, updated ${result.updated_count}, from ${result.sync_start_date || "latest window"}.`
    );
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
          <button className="secondary" onClick={syncLatest}>
            <RefreshCcw size={16} /> Sync latest
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

      <section className="panel">
        <h2>Data Freshness</h2>
        <div className="metadata-grid">
          <span>Latest request</span><strong>{summary?.latest_created_date ? new Date(summary.latest_created_date).toLocaleString() : "n/a"}</strong>
          <span>Last successful sync</span><strong>{summary?.latest_ingestion_finished_at ? new Date(summary.latest_ingestion_finished_at).toLocaleString() : "n/a"}</strong>
        </div>
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
