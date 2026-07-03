type DemoTrace = {
  id: number;
  user_query: string;
  route: string;
  selected_tool: string;
  status: string;
  latency_ms: number;
  created_at: string;
};

const now = () => new Date().toISOString();

const traces: DemoTrace[] = [
  {
    id: 3,
    user_query: "What policy explains allowed SQL statements?",
    route: "rag",
    selected_tool: "rag_policy_assistant",
    status: "success",
    latency_ms: 41,
    created_at: now()
  },
  {
    id: 2,
    user_query: "What are the top complaint types?",
    route: "sql",
    selected_tool: "safe_sql_analysis",
    status: "success",
    latency_ms: 18,
    created_at: now()
  },
  {
    id: 1,
    user_query: "Import 311 service requests",
    route: "ingestion",
    selected_tool: "nyc_311_ingestion",
    status: "success",
    latency_ms: 1040,
    created_at: now()
  }
];

const dashboardSummary = {
  total_requests: 3000,
  open_requests: 842,
  closed_requests: 2158,
  average_resolution_hours: 37.4,
  latest_created_date: "2026-07-03T18:30:00",
  latest_ingestion_finished_at: now(),
  top_complaints: [
    { label: "Noise - Residential", value: 612 },
    { label: "Illegal Parking", value: 438 },
    { label: "HEAT/HOT WATER", value: 391 },
    { label: "Blocked Driveway", value: 244 }
  ],
  borough_distribution: [
    { label: "BROOKLYN", value: 1034 },
    { label: "QUEENS", value: 796 },
    { label: "MANHATTAN", value: 611 },
    { label: "BRONX", value: 424 },
    { label: "STATEN ISLAND", value: 135 }
  ],
  agency_workload: [
    { label: "NYPD", value: 1128 },
    { label: "HPD", value: 764 },
    { label: "DSNY", value: 418 },
    { label: "DOT", value: 306 }
  ],
  daily_trend: [
    { label: "2026-07-03", value: 418 },
    { label: "2026-07-02", value: 392 },
    { label: "2026-07-01", value: 447 },
    { label: "2026-06-30", value: 365 }
  ]
};

const ragCitations = [
  {
    document_title: "Civicops Agent Operating Policy",
    chunk_id: 1,
    heading: "Safe SQL",
    source_url: null,
    snippet:
      "The CivicOps Agent may execute read-only SELECT queries for analysis. It must not execute INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE, or other destructive database statements.",
    score: 0.42,
    lexical_score: 0.31,
    vector_score: 0.49,
    matched_terms: ["sql", "select", "execute"]
  },
  {
    document_title: "Civicops Agent Operating Policy",
    chunk_id: 2,
    heading: "Tool Calling",
    source_url: null,
    snippet:
      "The language model or router can select tools, but the backend owns tool execution. The backend validates tool inputs, enforces SQL safety, records execution traces, and returns structured outputs.",
    score: 0.34,
    lexical_score: 0.2,
    vector_score: 0.45,
    matched_terms: ["tool", "sql", "execution"]
  }
];

function sqlResponse(question: string) {
  return {
    question,
    generated_sql:
      "SELECT complaint_type, COUNT(*) AS request_count FROM service_requests WHERE complaint_type IS NOT NULL GROUP BY complaint_type ORDER BY request_count DESC LIMIT 10",
    confidence: 0.9,
    assumptions: [
      "Using table service_requests.",
      "Only read-only SELECT SQL is generated.",
      "Planner provider: deterministic template fallback.",
      "Ranking complaint_type by count."
    ],
    result: {
      columns: ["complaint_type", "request_count"],
      rows: dashboardSummary.top_complaints.map((item) => ({ complaint_type: item.label, request_count: item.value })),
      row_count: dashboardSummary.top_complaints.length
    },
    answer: "Returned 4 rows. The top row is: complaint_type=Noise - Residential, request_count=612.",
    trace_id: 2
  };
}

function ragResponse(question: string) {
  return {
    question,
    answer:
      "Based on the retrieved evidence, CivicOps only allows read-only SELECT queries for analysis. Destructive statements such as INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, and REVOKE are blocked before execution.",
    citations: ragCitations,
    confidence: 0.84,
    refused: false,
    retrieval_method: "hybrid_bm25_vector_rerank",
    generation_provider: "mock",
    trace_id: 3
  };
}

export async function demoApi<T>(path: string, options?: RequestInit): Promise<T> {
  const method = options?.method?.toUpperCase() || "GET";
  const body = options?.body ? JSON.parse(String(options.body)) : {};

  if (path === "/health") {
    return { status: "ok", service: "civicops-demo", version: "1.0.0", environment: "github-pages-demo" } as T;
  }
  if (path === "/dashboard/summary") {
    return dashboardSummary as T;
  }
  if (path === "/ingestion/run" && method === "POST") {
    return {
      run_id: 1,
      source: "nyc_311_demo_snapshot",
      requested_limit: body.limit || 1000,
      fetched_count: body.limit || 1000,
      inserted_count: body.limit || 1000,
      updated_count: 0,
      status: "success",
      error_message: null,
      started_at: now(),
      finished_at: now()
    } as T;
  }
  if (path === "/ingestion/sync-latest" && method === "POST") {
    return {
      run_id: 4,
      source: "nyc_311_demo_snapshot",
      requested_limit: body.limit || 5000,
      fetched_count: 5000,
      inserted_count: 140,
      updated_count: 4860,
      status: "success",
      error_message: null,
      started_at: now(),
      finished_at: now(),
      sync_mode: "latest_with_lookback",
      previous_latest_created_date: dashboardSummary.latest_created_date,
      sync_start_date: "2026-06-26"
    } as T;
  }
  if (path === "/agent/sql" && method === "POST") {
    return sqlResponse(body.question || "What are the top complaint types?") as T;
  }
  if (path === "/agent/route" && method === "POST") {
    return {
      route: "rag",
      reason: "The question asks for policy/process knowledge that needs document evidence.",
      selected_tool: "rag_policy_assistant",
      planner_provider: "heuristic",
      plan_steps: [
        "Identify the question as a document-grounded policy/process request.",
        "Retrieve relevant chunks with BM25, vector similarity, query expansion, and reranking.",
        "Generate a grounded answer with citations or refuse weak evidence."
      ],
      confidence: 0.76,
      response: ragResponse(body.question || "What policy explains allowed SQL statements?"),
      trace_id: 3
    } as T;
  }
  if (path === "/rag/reindex" && method === "POST") {
    return {
      documents_indexed: 133,
      chunks_indexed: 1802,
      local_sources_indexed: 6,
      remote_sources_indexed: 127,
      embedding_provider: "local_hash",
      embedding_model: "local-hash-384",
      warnings: []
    } as T;
  }
  if (path === "/rag/ask" && method === "POST") {
    return ragResponse(body.question || "What SQL statements is the agent allowed to execute?") as T;
  }
  if (path === "/traces") {
    return traces as T;
  }
  if (path === "/evals/run" && method === "POST") {
    return {
      metrics: [
        { name: "sql_safety_pass_rate", passed: 6, total: 6, score: 1 },
        { name: "rag_citation_and_refusal_rate", passed: 3, total: 3, score: 1 }
      ],
      failures: []
    } as T;
  }
  throw new Error(`Demo API route is not implemented: ${method} ${path}`);
}
