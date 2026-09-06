// Mirrors backend/app/schemas/api.py - kept in sync by hand (docs/tech-stack.md: no
// generated-client tooling added without a concrete need for it).

export interface AgentVersionSummary {
  id: string;
  version_label: string;
  description: string | null;
  created_at: string;
}

export interface AgentSummary {
  id: string;
  name: string;
  description: string | null;
  adapter_key: string;
  versions: AgentVersionSummary[];
}

export interface DatasetSummary {
  id: string;
  name: string;
  description: string | null;
  case_count: number;
}

export interface DatasetCaseSummary {
  id: string;
  key: string;
  tags: string[];
}

export interface DatasetDetail extends DatasetSummary {
  cases: DatasetCaseSummary[];
}

export interface EvaluatorSummary {
  id: string;
  key: string;
  version: string;
  type: string;
  dimension: string;
  description: string | null;
}

export interface RunListItem {
  id: string;
  agent_version_id: string;
  dataset_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  triggered_by: string | null;
}

export interface DimensionStats {
  dimension: string;
  mean_score: number | null;
  n: number;
  n_not_applicable: number;
}

export interface CaseRunSummary {
  case_run_id: string;
  case_key: string;
  status: string;
  latency_ms: number;
}

export interface RunSummary {
  id: string;
  agent_version_id: string;
  dataset_id: string;
  dataset_snapshot_hash: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  triggered_by: string | null;
  dimension_stats: DimensionStats[];
  case_runs: CaseRunSummary[];
}

export interface ToolCallDetail {
  sequence_index: number;
  tool_name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown> | null;
  status: string;
  latency_ms: number | null;
}

export interface EvaluationResultDetail {
  evaluator_key: string;
  evaluator_version: string;
  dimension: string;
  score: number;
  passed: boolean | null;
  reasoning: string | null;
}

export interface TraceStep {
  step_type: string;
  timestamp: string | null;
  payload: Record<string, unknown>;
}

export interface CaseRunDetail {
  case_run_id: string;
  case_key: string;
  case_input: Record<string, unknown>;
  case_expected: Record<string, unknown>;
  status: string;
  final_output: string | null;
  structured_output: Record<string, unknown> | null;
  normalized_trace: TraceStep[];
  latency_ms: number;
  token_usage: Record<string, unknown> | null;
  cost_usd: number | null;
  error: Record<string, unknown> | null;
  tool_calls: ToolCallDetail[];
  evaluation_results: EvaluationResultDetail[];
}

export interface CaseComparisonEntry {
  case_key: string;
  dimension: string;
  run_a_score: number | null;
  run_a_passed: boolean | null;
  run_b_score: number | null;
  run_b_passed: boolean | null;
}

export interface EvaluatorVersionMismatch {
  dimension: string;
  evaluator_key: string;
  run_a_version: string;
  run_b_version: string;
}

export interface ComparisonResponse {
  run_a_id: string;
  run_b_id: string;
  dataset_id: string;
  dataset_drift_detected: boolean;
  evaluator_version_mismatches: EvaluatorVersionMismatch[];
  dimension_stats: DimensionStats[];
  regressions: CaseComparisonEntry[];
  improvements: CaseComparisonEntry[];
}

export interface TriggerRunRequest {
  agent_version_id: string;
  dataset_id: string;
  evaluator_ids: string[];
  triggered_by?: string;
  timeout_seconds?: number;
}
