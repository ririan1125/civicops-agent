import React from "react";
import { Search } from "lucide-react";
import { api } from "../api";
import type { SQLResponse } from "../types";

export function SQLAgent() {
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
        <h1>Safe SQL Tool</h1>
        <p>Questions are planned against the service_requests schema, validated as read-only SQL, executed, and traced.</p>
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
          <ul className="plan-list">
            {result.assumptions.map((item) => <li key={item}>{item}</li>)}
          </ul>
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
