# NYC Open Data PDF Source Notes

Source type: bundled notes for official NYC Open Data PDF sources.

## Official PDF Sources

The RAG index attempts to fetch these official PDF documents during remote reindex:

- NYC Open Data Technical Standards Manual: https://opendata.cityofnewyork.us/wp-content/uploads/NYC_OpenData_TechnicalStandardsManual.pdf
- NYC Open Data Quality Standards and Review Process: https://opendata.cityofnewyork.us/wp-content/uploads/OpenDataQualityStandards_Review-Process.pdf

The same Technical Standards Manual content is also indexed from the official GitHub Pages version at https://cityofnewyork.github.io/opendatatsm/ because the city PDF host can return 403 to backend clients.

## Why These Documents Matter

These official policy documents are relevant to CivicOps Agent because the system uses NYC Open Data as its source of truth for 311 service requests.

They help answer governance questions such as:

- what metadata and documentation should accompany an open dataset;
- why stable field definitions and machine-readable formats matter;
- how dataset quality, review, and publication standards affect downstream analysis;
- why the agent should not invent facts when the indexed evidence or structured data is incomplete.

## RAG Boundary

This note is not a replacement for the official PDFs. It is a stable source pointer and retrieval fallback. When the PDF fetch succeeds, the extracted PDF text is indexed as an additional remote document with its official source URL.
