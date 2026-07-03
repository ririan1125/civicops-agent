# NYC 311 Service Guidance Sample

## Purpose

NYC 311 service request data is used to understand operational demand, complaint hotspots, agency workload, and service resolution patterns. Analysts should use aggregated metrics rather than individual records when reporting public-facing trends.

## Triage Guidelines

Requests with unresolved safety-related complaint types, repeated incidents in the same borough, or unusually long open duration should be reviewed with higher priority. Human review is required before creating or escalating operational tasks.

## Data Quality Rules

Analysts should check missing borough, status, complaint type, latitude, and longitude fields before drawing conclusions. Date fields can be incomplete, so resolution time metrics should only use records with both created date and closed date.

## RAG Answering Policy

The assistant must answer policy or process questions only when relevant document evidence is retrieved. If the retrieved evidence is weak, the assistant should say that it cannot answer confidently from the indexed documents.
