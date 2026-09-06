// Thin server-side API client (docs/tech-stack.md: no state-management library, no
// generated client - the frontend is a thin client of the backend API). Every function
// here runs on the Next.js server (Server Components, Server Actions), never in the
// browser, so CORS and client-side loading states are not this file's problem.

import type {
  AgentSummary,
  CaseRunDetail,
  ComparisonResponse,
  DatasetDetail,
  DatasetSummary,
  EvaluatorSummary,
  RunListItem,
  RunSummary,
  TriggerRunRequest,
} from "./types";

const API_BASE_URL = process.env.AGENT_EVAL_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    cache: "no-store", // dev tool over frequently-changing data - never serve stale runs
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${init?.method ?? "GET"} ${path} failed (${response.status}): ${body}`);
  }
  return response.json() as Promise<T>;
}

export function listAgents(): Promise<AgentSummary[]> {
  return apiFetch("/agents");
}

export function listDatasets(): Promise<DatasetSummary[]> {
  return apiFetch("/datasets");
}

export function getDataset(id: string): Promise<DatasetDetail> {
  return apiFetch(`/datasets/${id}`);
}

export function listEvaluators(): Promise<EvaluatorSummary[]> {
  return apiFetch("/evaluators");
}

export function listRuns(params: { datasetId?: string; agentVersionId?: string; limit?: number } = {}): Promise<RunListItem[]> {
  const search = new URLSearchParams();
  if (params.datasetId) search.set("dataset_id", params.datasetId);
  if (params.agentVersionId) search.set("agent_version_id", params.agentVersionId);
  if (params.limit) search.set("limit", String(params.limit));
  const qs = search.toString();
  return apiFetch(`/runs${qs ? `?${qs}` : ""}`);
}

export function triggerRun(body: TriggerRunRequest): Promise<RunSummary> {
  return apiFetch("/runs", { method: "POST", body: JSON.stringify(body) });
}

export function getRun(id: string, tag?: string): Promise<RunSummary> {
  return apiFetch(`/runs/${id}${tag ? `?tag=${encodeURIComponent(tag)}` : ""}`);
}

export function getCaseRun(runId: string, caseRunId: string): Promise<CaseRunDetail> {
  return apiFetch(`/runs/${runId}/cases/${caseRunId}`);
}

export function compareRuns(runAId: string, runBId: string): Promise<ComparisonResponse> {
  const search = new URLSearchParams({ run_a_id: runAId, run_b_id: runBId });
  return apiFetch(`/runs/compare?${search.toString()}`);
}

/** Small display helper built from the catalog endpoints - not its own backend endpoint,
 * since it's just a lookup table over data GET /agents and GET /datasets already return. */
export async function buildCatalogLookup() {
  const [agents, datasets] = await Promise.all([listAgents(), listDatasets()]);
  const agentVersionLabel = new Map<string, string>();
  for (const agent of agents) {
    for (const version of agent.versions) {
      agentVersionLabel.set(version.id, `${agent.name} @ ${version.version_label}`);
    }
  }
  const datasetName = new Map(datasets.map((d) => [d.id, d.name] as const));
  return { agents, datasets, agentVersionLabel, datasetName };
}
