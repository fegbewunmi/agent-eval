import Link from "next/link";
import { buildCatalogLookup, getDataset, getRun } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

export default async function RunPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tag?: string }>;
}) {
  const { id } = await params;
  const { tag } = await searchParams;
  const run = await getRun(id, tag);

  const [{ agentVersionLabel, datasetName }, dataset] = await Promise.all([
    buildCatalogLookup(),
    getDataset(run.dataset_id),
  ]);
  const allTags = Array.from(new Set(dataset.cases.flatMap((c) => c.tags))).sort();

  return (
    <section>
      <h1>Run {run.id.slice(0, 8)}</h1>
      <p className="muted">
        {agentVersionLabel.get(run.agent_version_id) ?? run.agent_version_id} against{" "}
        {datasetName.get(run.dataset_id) ?? run.dataset_id} - <StatusBadge status={run.status} />
      </p>
      <p className="muted">
        started {run.started_at ? new Date(run.started_at).toLocaleString() : "-"}
        {run.completed_at && <> - completed {new Date(run.completed_at).toLocaleString()}</>}
        {run.triggered_by && <> - triggered by {run.triggered_by}</>}
      </p>
      <p>
        <Link href={`/runs/compare?run_a_id=${run.id}`}>Compare this run against another</Link>
      </p>

      {allTags.length > 0 && (
        <p>
          <Link href={`/runs/${run.id}`} className={`tag-chip ${!tag ? "active" : ""}`}>
            all cases
          </Link>
          {allTags.map((t) => (
            <Link key={t} href={`/runs/${run.id}?tag=${encodeURIComponent(t)}`} className={`tag-chip ${tag === t ? "active" : ""}`}>
              {t}
            </Link>
          ))}
        </p>
      )}

      <h2>Per-dimension summary</h2>
      <table>
        <thead>
          <tr>
            <th>Dimension</th>
            <th>Mean score</th>
            <th>n</th>
            <th>n/a</th>
          </tr>
        </thead>
        <tbody>
          {run.dimension_stats.map((stat) => (
            <tr key={stat.dimension}>
              <td>{stat.dimension}</td>
              <td>{stat.mean_score === null ? <span className="muted">n/a</span> : stat.mean_score.toFixed(2)}</td>
              <td>{stat.n}</td>
              <td className="muted">{stat.n_not_applicable}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Cases {tag && <span className="muted">(tag: {tag})</span>}</h2>
      <table>
        <thead>
          <tr>
            <th>Case</th>
            <th>Status</th>
            <th>Latency (ms)</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {run.case_runs.map((cr) => (
            <tr key={cr.case_run_id}>
              <td>{cr.case_key}</td>
              <td>
                <StatusBadge status={cr.status} />
              </td>
              <td>{cr.latency_ms.toFixed(1)}</td>
              <td>
                <Link href={`/runs/${run.id}/cases/${cr.case_run_id}`}>Inspect</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
