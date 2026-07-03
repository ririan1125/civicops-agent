import React from "react";
import { FileSearch, RefreshCcw } from "lucide-react";
import { api } from "../api";
import type { RAGResponse } from "../types";

export function RAGAssistant() {
  const [question, setQuestion] = React.useState("How do I check a NYC311 service request status?");
  const [result, setResult] = React.useState<RAGResponse | null>(null);
  const [status, setStatus] = React.useState("");
  const [warnings, setWarnings] = React.useState<string[]>([]);

  async function reindex() {
    const response = await api<{
      documents_indexed: number;
      chunks_indexed: number;
      local_sources_indexed: number;
      remote_sources_indexed: number;
      embedding_provider?: string;
      embedding_model?: string;
      warnings: string[];
    }>("/rag/reindex", {
      method: "POST",
      body: JSON.stringify({ include_remote: true, max_311_articles: 120 })
    });
    setWarnings(response.warnings || []);
    setStatus(
      `Indexed ${response.documents_indexed} documents (${response.local_sources_indexed} local, ${response.remote_sources_indexed} remote) and ${response.chunks_indexed} chunks with ${response.embedding_provider || "embedding"} / ${response.embedding_model || "model"}.`
    );
  }

  async function ask() {
    setResult(await api<RAGResponse>("/rag/ask", { method: "POST", body: JSON.stringify({ question, top_k: 4 }) }));
  }

  return (
    <main className="workspace">
      <section className="tool-header">
        <h1>Hybrid RAG Assistant</h1>
        <p>Official NYC311 pages and project documents are chunked, embedded, retrieved with BM25/vector reranking, and answered with citations.</p>
      </section>
      <div className="ask-row">
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
        <button onClick={ask}>
          <FileSearch size={16} /> Ask
        </button>
        <button className="secondary" onClick={reindex}>
          <RefreshCcw size={16} /> Refresh official docs
        </button>
      </div>
      {status ? <div className="status">{status}</div> : null}
      {warnings.length ? (
        <div className="status">
          {warnings.slice(0, 3).map((warning) => <div key={warning}>{warning}</div>)}
        </div>
      ) : null}
      {result ? (
        <section className="panel">
          <h2>{result.refused ? "Refused" : "Answer"}</h2>
          <p>{result.answer}</p>
          <div className="metadata-grid">
            <span>Retrieval</span><strong>{result.retrieval_method}</strong>
            <span>Generation</span><strong>{result.generation_provider}</strong>
            <span>Confidence</span><strong>{Math.round(result.confidence * 100)}%</strong>
            <span>Trace</span><strong>#{result.trace_id}</strong>
          </div>
          <div className="citations">
            {result.citations.map((citation) => (
              <article className="citation" key={citation.chunk_id}>
                <strong>{citation.document_title}</strong>
                <span>
                  {citation.heading || "Untitled section"} | hybrid {citation.score} | vector {citation.vector_score ?? "n/a"} | lexical {citation.lexical_score ?? "n/a"}
                </span>
                {citation.source_url ? <a href={citation.source_url} target="_blank" rel="noreferrer">Open source</a> : null}
                <p>{citation.snippet}</p>
                {citation.matched_terms.length ? <small>Matched terms: {citation.matched_terms.join(", ")}</small> : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}
