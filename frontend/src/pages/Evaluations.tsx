import React from "react";
import { FileSearch, ListChecks, Radar } from "lucide-react";
import { api } from "../api";
import { Metric } from "../components/Metric";
import type { EmbeddingBenchmarkResponse, EvalResponse, RetrievalEvalResponse } from "../types";

export function Evaluations() {
  const [result, setResult] = React.useState<EvalResponse | null>(null);
  const [retrieval, setRetrieval] = React.useState<RetrievalEvalResponse | null>(null);
  const [benchmark, setBenchmark] = React.useState<EmbeddingBenchmarkResponse | null>(null);

  async function run() {
    setResult(await api<EvalResponse>("/evals/run", { method: "POST" }));
  }

  async function runRetrieval() {
    setRetrieval(await api<RetrievalEvalResponse>("/evals/rag-retrieval", { method: "POST" }));
  }

  async function runBenchmark() {
    setBenchmark(await api<EmbeddingBenchmarkResponse>("/evals/embedding-benchmark", { method: "POST" }));
  }

  return (
    <main className="workspace">
      <section className="tool-header">
        <h1>Evaluation</h1>
        <p>SQL safety, RAG retrieval, embedding baselines, citation quality, and refusal behavior.</p>
      </section>
      <div className="action-row">
        <button onClick={run}>
          <ListChecks size={16} /> Run evals
        </button>
        <button className="secondary" onClick={runRetrieval}>
          <FileSearch size={16} /> Retrieval eval
        </button>
        <button className="secondary" onClick={runBenchmark}>
          <Radar size={16} /> Embedding benchmark
        </button>
      </div>
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
      {retrieval ? (
        <section className="panel">
          <h2>Retrieval</h2>
          <div className="metadata-grid">
            <span>Embedding</span><strong>{retrieval.embedding_provider} / {retrieval.embedding_model}</strong>
            {retrieval.metrics.map((metric) => (
              <React.Fragment key={metric.name}>
                <span>{metric.name}</span><strong>{Math.round(metric.score * 100)}%</strong>
              </React.Fragment>
            ))}
          </div>
          <pre>{JSON.stringify(retrieval.cases.slice(0, 5), null, 2)}</pre>
        </section>
      ) : null}
      {benchmark ? (
        <section className="panel">
          <h2>Embedding</h2>
          <div className="metadata-grid">
            <span>Corpus chunks</span><strong>{benchmark.corpus_chunks}</strong>
            <span>Cases</span><strong>{benchmark.cases_count}</strong>
            <span>Best</span><strong>{benchmark.best_variant || "n/a"}</strong>
          </div>
          <section className="metric-grid">
            {benchmark.variants.map((variant) => {
              const mrr = variant.metrics.find((metric) => metric.name === "rag_mrr")?.score ?? 0;
              const recall = variant.metrics.find((metric) => metric.name === "rag_recall_at_1")?.score ?? 0;
              return (
                <Metric
                  key={variant.model}
                  label={variant.model}
                  value={`${Math.round(mrr * 100)}% MRR`}
                  helper={`Recall@1 ${Math.round(recall * 100)}%`}
                />
              );
            })}
          </section>
        </section>
      ) : null}
    </main>
  );
}
