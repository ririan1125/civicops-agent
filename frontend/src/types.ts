export type BreakdownItem = { label: string; value: number };

export type DashboardSummary = {
  total_requests: number;
  open_requests: number;
  closed_requests: number;
  average_resolution_hours: number | null;
  latest_created_date: string | null;
  latest_ingestion_finished_at: string | null;
  top_complaints: BreakdownItem[];
  borough_distribution: BreakdownItem[];
  agency_workload: BreakdownItem[];
  daily_trend: BreakdownItem[];
};

export type SQLResponse = {
  generated_sql: string;
  confidence: number;
  assumptions: string[];
  result: { columns: string[]; rows: Record<string, unknown>[]; row_count: number };
  answer: string;
  trace_id: number | null;
};

export type Citation = {
  document_title: string;
  chunk_id: number;
  heading: string | null;
  source_url?: string | null;
  snippet: string;
  score: number;
  lexical_score?: number | null;
  vector_score?: number | null;
  matched_terms: string[];
};

export type RAGResponse = {
  answer: string;
  citations: Citation[];
  confidence: number;
  refused: boolean;
  retrieval_method: string;
  generation_provider: string;
  trace_id: number | null;
};

export type AgentRouteResponse = {
  route: string;
  reason: string;
  selected_tool: string | null;
  planner_provider: string;
  plan_steps: string[];
  confidence: number | null;
  response: Record<string, unknown>;
  trace_id: number | null;
};

export type TraceRecord = {
  id: number;
  user_query: string;
  route: string;
  selected_tool: string;
  status: string;
  latency_ms: number;
  created_at: string;
};

export type EvalResponse = {
  metrics: { name: string; passed: number; total: number; score: number }[];
  failures: Record<string, unknown>[];
};
