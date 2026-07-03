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

Use:

```text
What are the top complaint types?
```

Then:

```text
Show borough distribution.
```

Explain:

- The agent maps natural language to a read-only SELECT.
- SQL is validated before execution.
- Generated SQL, result rows, assumptions, confidence, and trace ID are returned.

## 5. Ask The RAG Assistant

Click **Reindex docs**, then ask:

```text
What SQL statements is the agent allowed to execute?
```

Explain:

- The RAG assistant chunks local policy documents.
- It retrieves evidence and returns citations.
- If evidence is weak, it refuses instead of guessing.

## 6. Show Traces

Open the Traces tab.

Explain:

- Each agent action records user query, route, tool, input, output, status, latency, and errors.
- This supports debugging, auditing, and evaluation.

## 7. Run Evaluation

Open the Evals tab and run evals.

Explain:

- SQL safety cases measure whether dangerous SQL is blocked.
- RAG cases measure citation and refusal behavior.
