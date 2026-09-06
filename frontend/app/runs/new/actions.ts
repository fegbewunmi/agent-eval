"use server";

import { redirect } from "next/navigation";
import { triggerRun } from "@/lib/api";

export async function triggerRunAction(formData: FormData): Promise<void> {
  const agentVersionId = formData.get("agent_version_id");
  const datasetId = formData.get("dataset_id");
  const evaluatorIds = formData.getAll("evaluator_ids").map(String);
  const triggeredBy = formData.get("triggered_by");
  const timeoutSeconds = formData.get("timeout_seconds");

  if (typeof agentVersionId !== "string" || !agentVersionId) {
    throw new Error("Select an agent version.");
  }
  if (typeof datasetId !== "string" || !datasetId) {
    throw new Error("Select a dataset.");
  }
  if (evaluatorIds.length === 0) {
    throw new Error("Select at least one evaluator.");
  }

  const run = await triggerRun({
    agent_version_id: agentVersionId,
    dataset_id: datasetId,
    evaluator_ids: evaluatorIds,
    triggered_by: typeof triggeredBy === "string" && triggeredBy ? triggeredBy : undefined,
    timeout_seconds:
      typeof timeoutSeconds === "string" && timeoutSeconds ? Number(timeoutSeconds) : undefined,
  });

  // run_evaluation is synchronous (ADR-0005) - this Server Action only resolves once the
  // whole run has finished, so the redirect below lands on a completed run's summary.
  redirect(`/runs/${run.id}`);
}
