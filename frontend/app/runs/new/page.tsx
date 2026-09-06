import { listAgents, listDatasets, listEvaluators } from "@/lib/api";
import { triggerRunAction } from "./actions";

export default async function NewRunPage() {
  const [agents, datasets, evaluators] = await Promise.all([listAgents(), listDatasets(), listEvaluators()]);

  return (
    <section>
      <h1>Trigger a new run</h1>
      <p className="muted">
        Runs execute synchronously (ADR-0005) - for the real Incident Investigation Platform
        adapter this can take several minutes; the page will navigate to the run once it
        completes.
      </p>

      <form className="stack" action={triggerRunAction}>
        <label>
          Agent version
          <select name="agent_version_id" required defaultValue="">
            <option value="" disabled>
              Select an agent version
            </option>
            {agents.flatMap((agent) =>
              agent.versions.map((version) => (
                <option key={version.id} value={version.id}>
                  {agent.name} @ {version.version_label}
                </option>
              ))
            )}
          </select>
        </label>

        <label>
          Dataset
          <select name="dataset_id" required defaultValue="">
            <option value="" disabled>
              Select a dataset
            </option>
            {datasets.map((dataset) => (
              <option key={dataset.id} value={dataset.id}>
                {dataset.name} ({dataset.case_count} cases)
              </option>
            ))}
          </select>
        </label>

        <label>
          Evaluators
          <div className="checkbox-list">
            {evaluators.map((evaluator) => (
              <label key={evaluator.id}>
                <input type="checkbox" name="evaluator_ids" value={evaluator.id} />
                <code>{evaluator.key}</code> {evaluator.version} - {evaluator.dimension}
              </label>
            ))}
          </div>
        </label>

        <label>
          Timeout per case (seconds)
          <input type="number" name="timeout_seconds" defaultValue={200} min={1} />
          <span className="muted" style={{ fontWeight: "normal" }}>
            30s is enough for the stub agent; the real Incident Investigation Platform
            adapter needs 180s+ per case (multiple real LLM calls) - lower this only for
            fast/free adapters.
          </span>
        </label>

        <label>
          Triggered by (optional)
          <input type="text" name="triggered_by" placeholder="your name" />
        </label>

        <button type="submit">Trigger run</button>
      </form>
    </section>
  );
}
