import React from "react";
import { Bot } from "lucide-react";
import { api } from "../api";
import type { AgentRouteResponse } from "../types";

export function AgentRun() {
  const [question, setQuestion] = React.useState("What policy explains allowed SQL statements?");
  const [result, setResult] = React.useState<AgentRouteResponse | null>(null);
  const [error, setError] = React.useState("");

  async function run() {
    try {
      setError("");
      setResult(await api<AgentRouteResponse>("/agent/route", { method: "POST", body: JSON.stringify({ question }) }));
    } catch (error) {
      setError(error instanceof Error ? error.message : "Agent run failed.");
    }
  }

  return (
    <main className="workspace">
      <section className="tool-header">
        <h1>Agent Run</h1>
        <p>Planner selects a tool, executes it, and records the chosen route, plan steps, output, and trace.</p>
      </section>
      <div className="ask-row">
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
        <button onClick={run}>
          <Bot size={16} /> Run
        </button>
      </div>
      {error ? <div className="error">{error}</div> : null}
      {result ? (
        <section className="panel">
          <h2>Planner Decision</h2>
          <div className="metadata-grid">
            <span>Route</span><strong>{result.route}</strong>
            <span>Tool</span><strong>{result.selected_tool}</strong>
            <span>Planner</span><strong>{result.planner_provider}</strong>
            <span>Confidence</span><strong>{result.confidence === null ? "n/a" : `${Math.round(result.confidence * 100)}%`}</strong>
            <span>Trace</span><strong>#{result.trace_id}</strong>
          </div>
          <p>{result.reason}</p>
          <ol className="plan-list">
            {result.plan_steps.map((step) => <li key={step}>{step}</li>)}
          </ol>
          <h2>Tool Output</h2>
          <pre>{JSON.stringify(result.response, null, 2)}</pre>
        </section>
      ) : null}
    </main>
  );
}
