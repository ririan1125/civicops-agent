import React from "react";
import { ListChecks } from "lucide-react";
import { api } from "../api";
import { Metric } from "../components/Metric";
import type { EvalResponse } from "../types";

export function Evaluations() {
  const [result, setResult] = React.useState<EvalResponse | null>(null);

  async function run() {
    setResult(await api<EvalResponse>("/evals/run", { method: "POST" }));
  }

  return (
    <main className="workspace">
      <section className="tool-header">
        <h1>Evaluation</h1>
        <p>SQL safety, RAG retrieval/citation, and refusal behavior are checked with fixed eval cases.</p>
      </section>
      <button onClick={run}>
        <ListChecks size={16} /> Run evals
      </button>
      {result ? (
        <>
          <section className="metric-grid">
            {result.metrics.map((metric) => (
              <Metric key={metric.name} label={metric.name} value={`${Math.round(metric.score * 100)}%`} helper={`${metric.passed}/${metric.total} passed`} />
            ))}
          </section>
          {result.failures.length ? <pre>{JSON.stringify(result.failures, null, 2)}</pre> : null}
        </>
      ) : null}
    </main>
  );
}
