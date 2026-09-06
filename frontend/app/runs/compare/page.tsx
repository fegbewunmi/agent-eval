import Link from "next/link";
import { buildCatalogLookup, compareRuns, listRuns } from "@/lib/api";

function runLabel(
  run: { id: string; agent_version_id: string; dataset_id: string; status: string },
  agentVersionLabel: Map<string, string>,
  datasetName: Map<string, string>
) {
  return `${run.id.slice(0, 8)} - ${agentVersionLabel.get(run.agent_version_id) ?? run.agent_version_id} - ${
    datasetName.get(run.dataset_id) ?? run.dataset_id
  } (${run.status})`;
}

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ run_a_id?: string; run_b_id?: string }>;
}) {
  const { run_a_id, run_b_id } = await searchParams;
  const [runs, { agentVersionLabel, datasetName }] = await Promise.all([listRuns({ limit: 100 }), buildCatalogLookup()]);

  return (
    <section>
      <h1>Compare two runs</h1>
      <p className="muted">
        Regressions are surfaced before aggregate deltas (docs/evaluation-methodology.md) - a
        version that improves the mean while regressing specific cases has not
        unambiguously gotten better.
      </p>

      <form className="stack" method="get">
        <label>
          Run A (baseline)
          <select name="run_a_id" defaultValue={run_a_id ?? ""} required>
            <option value="" disabled>
              Select a run
            </option>
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {runLabel(run, agentVersionLabel, datasetName)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Run B (candidate)
          <select name="run_b_id" defaultValue={run_b_id ?? ""} required>
            <option value="" disabled>
              Select a run
            </option>
            {runs.map((run) => (
              <option key={run.id} value={run.id}>
                {runLabel(run, agentVersionLabel, datasetName)}
              </option>
            ))}
          </select>
        </label>
        <button type="submit">Compare</button>
      </form>

      {run_a_id && run_b_id && (
        <ComparisonResult runAId={run_a_id} runBId={run_b_id} />
      )}
    </section>
  );
}

async function ComparisonResult({ runAId, runBId }: { runAId: string; runBId: string }) {
  const comparison = await compareRuns(runAId, runBId);

  return (
    <div>
      {comparison.dataset_drift_detected && (
        <div className="alert alert-warn">
          Dataset drift detected: these two runs used different content for the same
          dataset (ADR-0003). This comparison may be confounded by dataset changes, not
          just the agent.
        </div>
      )}
      {comparison.evaluator_version_mismatches.map((m) => (
        <div className="alert alert-warn" key={`${m.dimension}-${m.evaluator_key}`}>
          Evaluator version mismatch on <strong>{m.dimension}</strong>: run A used{" "}
          <code>{m.evaluator_key}</code> {m.run_a_version}, run B used {m.run_b_version}
          (ADR-0008). This comparison may be confounded by an evaluator change, not just the
          agent.
        </div>
      ))}

      <h2>Regressions ({comparison.regressions.length})</h2>
      {comparison.regressions.length === 0 ? (
        <p className="muted">None.</p>
      ) : (
        <ComparisonTable rows={comparison.regressions} />
      )}

      <h2>Improvements ({comparison.improvements.length})</h2>
      {comparison.improvements.length === 0 ? (
        <p className="muted">None.</p>
      ) : (
        <ComparisonTable rows={comparison.improvements} />
      )}

      <h2>Run B per-dimension summary</h2>
      <p className="muted">Run A&apos;s own summary is one click away on its run page.</p>
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
          {comparison.dimension_stats.map((stat) => (
            <tr key={stat.dimension}>
              <td>{stat.dimension}</td>
              <td>{stat.mean_score === null ? <span className="muted">n/a</span> : stat.mean_score.toFixed(2)}</td>
              <td>{stat.n}</td>
              <td className="muted">{stat.n_not_applicable}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p>
        <Link href={`/runs/${runAId}`}>View run A</Link> - <Link href={`/runs/${runBId}`}>View run B</Link>
      </p>
    </div>
  );
}

function ComparisonTable({
  rows,
}: {
  rows: { case_key: string; dimension: string; run_a_passed: boolean | null; run_b_passed: boolean | null }[];
}) {
  return (
    <table>
      <thead>
        <tr>
          <th>Case</th>
          <th>Dimension</th>
          <th>Run A</th>
          <th>Run B</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            <td>{row.case_key}</td>
            <td>{row.dimension}</td>
            <td>
              <span className={`badge ${row.run_a_passed ? "badge-pass" : "badge-fail"}`}>
                {row.run_a_passed ? "pass" : "fail"}
              </span>
            </td>
            <td>
              <span className={`badge ${row.run_b_passed ? "badge-pass" : "badge-fail"}`}>
                {row.run_b_passed ? "pass" : "fail"}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
