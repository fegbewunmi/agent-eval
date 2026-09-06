import Link from "next/link";
import { buildCatalogLookup, listRuns } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

export default async function DashboardPage() {
  const [runs, { agents, datasets, agentVersionLabel, datasetName }] = await Promise.all([
    listRuns({ limit: 25 }),
    buildCatalogLookup(),
  ]);

  return (
    <section>
      <h1>Recent runs</h1>
      <p className="muted">
        {agents.length} agent(s) and {datasets.length} dataset(s) registered.{" "}
        <Link href="/runs/new">Trigger a new run</Link> or <Link href="/runs/compare">compare two runs</Link>.
      </p>

      {runs.length === 0 ? (
        <p className="muted">No runs yet - trigger one to get started.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Agent version</th>
              <th>Dataset</th>
              <th>Status</th>
              <th>Started</th>
              <th>Triggered by</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id}>
                <td>{agentVersionLabel.get(run.agent_version_id) ?? run.agent_version_id}</td>
                <td>{datasetName.get(run.dataset_id) ?? run.dataset_id}</td>
                <td>
                  <StatusBadge status={run.status} />
                </td>
                <td>{run.started_at ? new Date(run.started_at).toLocaleString() : "-"}</td>
                <td className="muted">{run.triggered_by ?? "-"}</td>
                <td>
                  <Link href={`/runs/${run.id}`}>View</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
