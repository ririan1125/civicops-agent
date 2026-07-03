# CivicOps Agent Operating Policy

## Safe SQL

The CivicOps Agent may execute read-only SELECT queries for analysis. It must not execute INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, or other destructive database statements.

## Tool Calling

The language model or router can select tools, but the backend owns tool execution. The backend validates tool inputs, enforces SQL safety, records execution traces, and returns structured outputs to the user interface.

## Human In The Loop

Priority recommendations are advisory. A human operator must approve any escalation, external task creation, or workflow action that could affect real operations.

## Execution Trace

Every agent action should record the user query, selected route, selected tool, tool input, tool output, status, latency, and error message when present. Traces are used for debugging, auditing, and evaluation.
