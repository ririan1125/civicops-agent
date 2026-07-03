import React from "react";
import ReactDOM from "react-dom/client";
import { Activity, BarChart3, Database, FileSearch, ListChecks, Route, Search } from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

type BreakdownItem = { label: string; value: number };
type DashboardSummary = {
  total_requests: number;
  open_requests: number;
  closed_requests: number;
  average_resolution_hours: number | null;
  top_complaints: BreakdownItem[];
  borough_distribution: BreakdownItem[];
  agency_workload: BreakdownItem[];
  daily_trend: BreakdownItem[];
};
type SQLResponse = {
  generated_sql: string;
  confidence: number;
  assumptions: string[];
  result: { columns: string[]; rows: Record<string, unknown>[]; row_count: number };
  answer: string;
  trace_id: number | null;
};
type Citation = { document_title: string; chunk_id: number; heading: string | null; snippet: string; score: number };
type RAGResponse = { answer: string; citations: Citation[]; confidence: number; refused: boolean; trace_id: number | null };
type TraceRecord = {
  id: number;
  user_query: string;
  route: string;
  selected_tool: string;
  status: string;
  latency_ms: number;
  created_at: string;
};
type EvalResponse = {
  metrics: { name: string; passed: number; total: number; score: number }[];
  failures: Record<string, unknown>[];
};

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || response.statusText);
  }
  return response.json();
}

function Metric({ label, value, helper }: { label: string; value: string | number; helper?: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {helper ? <small>{helper}</small> : null}
    </div>
  );
}

function Bars({ title, items }: { title: string; items: BreakdownItem[] }) {
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

function Dashboard() {
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
          <p>Urban service request analytics, safe SQL agent, RAG policy assistant, and traceable operations workflow.</p>
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

function SQLAgent() {
  const [question, setQuestion] = React.useState("What are the top complaint types?");
  const [result, setResult] = React.useState<SQLResponse | null>(null);
  const [error, setError] = React.useState("");

  async function ask() {
    try {
      setError("");
      setResult(await api<SQLResponse>("/agent/sql", { method: "POST", body: JSON.stringify({ question }) }));
    } catch (error) {
      setError(error instanceof Error ? error.message : "SQL agent request failed.");
    }
  }

  return (
    <main className="workspace">
      <section className="tool-header">
        <h1>Safe SQL Agent</h1>
        <p>Natural language metrics are mapped to read-only SQL, validated, executed, and recorded as traces.</p>
      </section>
      <div className="ask-row">
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
        <button onClick={ask}>
          <Search size={16} /> Ask
        </button>
      </div>
      {error ? <div className="error">{error}</div> : null}
      {result ? (
        <section className="panel">
          <h2>Answer</h2>
          <p>{result.answer}</p>
          <pre>{result.generated_sql}</pre>
          <p className="muted">Confidence: {Math.round(result.confidence * 100)}% · Trace #{result.trace_id}</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>{result.result.columns.map((column) => <th key={column}>{column}</th>)}</tr>
              </thead>
              <tbody>
                {result.result.rows.map((row, index) => (
                  <tr key={index}>
                    {result.result.columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </main>
  );
}

function RAGAssistant() {
  const [question, setQuestion] = React.useState("What SQL statements is the agent allowed to execute?");
  const [result, setResult] = React.useState<RAGResponse | null>(null);
  const [status, setStatus] = React.useState("");

  async function reindex() {
    const response = await api<{ documents_indexed: number; chunks_indexed: number }>("/rag/reindex", { method: "POST" });
    setStatus(`Indexed ${response.documents_indexed} documents and ${response.chunks_indexed} chunks.`);
  }

  async function ask() {
    setResult(await api<RAGResponse>("/rag/ask", { method: "POST", body: JSON.stringify({ question, top_k: 4 }) }));
  }

  return (
    <main className="workspace">
      <section className="tool-header">
        <h1>RAG Policy Assistant</h1>
        <p>Questions are answered from indexed policy/process markdown with citations and weak-evidence refusal.</p>
      </section>
      <div className="ask-row">
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
        <button onClick={ask}>
          <FileSearch size={16} /> Ask
        </button>
        <button className="secondary" onClick={reindex}>Reindex docs</button>
      </div>
      {status ? <div className="status">{status}</div> : null}
      {result ? (
        <section className="panel">
          <h2>{result.refused ? "Refused" : "Answer"}</h2>
          <p>{result.answer}</p>
          <p className="muted">Confidence: {Math.round(result.confidence * 100)}% · Trace #{result.trace_id}</p>
          <div className="citations">
            {result.citations.map((citation) => (
              <article className="citation" key={citation.chunk_id}>
                <strong>{citation.document_title}</strong>
                <span>{citation.heading || "Untitled section"} · score {citation.score}</span>
                <p>{citation.snippet}</p>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </main>
  );
}

function Traces() {
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

function Evaluations() {
  const [result, setResult] = React.useState<EvalResponse | null>(null);

  async function run() {
    setResult(await api<EvalResponse>("/evals/run", { method: "POST" }));
  }

  return (
    <main className="workspace">
      <section className="tool-header">
        <h1>Evaluation</h1>
        <p>Fixed SQL safety and RAG citation/refusal cases turn quality into measurable evidence.</p>
      </section>
      <button onClick={run}>
        <ListChecks size={16} /> Run evals
      </button>
      {result ? (
        <section className="metric-grid">
          {result.metrics.map((metric) => (
            <Metric key={metric.name} label={metric.name} value={`${Math.round(metric.score * 100)}%`} helper={`${metric.passed}/${metric.total} passed`} />
          ))}
        </section>
      ) : null}
    </main>
  );
}

const tabs = [
  { id: "dashboard", label: "Dashboard", icon: BarChart3, view: <Dashboard /> },
  { id: "sql", label: "SQL Agent", icon: Search, view: <SQLAgent /> },
  { id: "rag", label: "RAG", icon: FileSearch, view: <RAGAssistant /> },
  { id: "traces", label: "Traces", icon: Route, view: <Traces /> },
  { id: "evals", label: "Evals", icon: ListChecks, view: <Evaluations /> }
];

function App() {
  const [active, setActive] = React.useState("dashboard");
  const current = tabs.find((tab) => tab.id === active) ?? tabs[0];

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">CO</span>
          <div>
            <strong>CivicOps</strong>
            <small>Agent Console</small>
          </div>
        </div>
        <nav>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button className={active === tab.id ? "active" : ""} key={tab.id} onClick={() => setActive(tab.id)} title={tab.label}>
                <Icon size={17} /> {tab.label}
              </button>
            );
          })}
        </nav>
      </aside>
      {current.view}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
