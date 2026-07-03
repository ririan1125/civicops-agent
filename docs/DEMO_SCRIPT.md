# CivicOps Agent Demo Script

## 1. Start The Stack

```powershell
docker compose up --build
```

Open:

- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs

## 2. Import Real NYC 311 Data

On the Dashboard tab, set import limit to `1000` or `3000`, then click **Import data**.

What this proves:

- The backend can call the official NYC Open Data API.
- Records are cleaned and stored in PostgreSQL.
- Dashboard metrics are computed from database rows, not hardcoded values.

## 3. Show Dashboard Metrics

Explain:

- Total / open / closed requests
- Top complaint types
- Borough distribution
- Agency workload
- Daily trend

## 4. Ask The Safe SQL Agent

Open **Agent Run** first and ask:

```text
What policy explains allowed SQL statements?
```

Explain:

- The planner chooses one tool: SQL, RAG, or clarification.
- The UI shows selected tool, planner provider, confidence, plan steps, output, and trace ID.
- If DeepSeek is configured, the planner can use the LLM; otherwise it uses the deterministic fallback planner.

## 5. Ask The Safe SQL Tool

Use:

```text
What are the top complaint types?
```

Then:

```text
Show borough distribution.
```

Explain:

- The SQL tool maps natural language to a read-only SELECT.
- If DeepSeek is configured, schema-aware SQL planning can be used before safety validation.
- SQL is validated before execution.
- Generated SQL, result rows, assumptions, confidence, and trace ID are returned.

## 6. Ask The Hybrid RAG Assistant

Click **Reindex docs**, then ask:

```text
What SQL statements is the agent allowed to execute?
```

Explain:

- The RAG assistant chunks local policy documents.
- It generates chunk embeddings and uses hybrid vector/keyword retrieval.
- It gates weak evidence before calling the chat provider.
- It returns citations with hybrid score, vector score, lexical score, and matched terms.
- If evidence is weak, it refuses instead of guessing.

## 7. Show Traces

Open the Traces tab.

Explain:

- Each agent action records user query, route, tool, input, output, status, latency, and errors.
- This supports debugging, auditing, and evaluation.

## 8. Run Evaluation

Open the Evals tab and run evals.

Explain:

- SQL safety cases measure whether dangerous SQL is blocked.
- RAG cases measure citation, evidence-term hit, and refusal behavior.
