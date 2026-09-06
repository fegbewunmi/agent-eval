import Link from "next/link";
import { getCaseRun } from "@/lib/api";
import { JsonBlock } from "@/components/JsonBlock";
import { PassBadge } from "@/components/PassBadge";
import { StatusBadge } from "@/components/StatusBadge";

export default async function CaseRunPage({
  params,
}: {
  params: Promise<{ id: string; caseRunId: string }>;
}) {
  const { id, caseRunId } = await params;
  const caseRun = await getCaseRun(id, caseRunId);

  return (
    <section>
      <p>
        <Link href={`/runs/${id}`}>&larr; back to run</Link>
      </p>
      <h1>{caseRun.case_key}</h1>
      <p className="muted">
        <StatusBadge status={caseRun.status} /> - {caseRun.latency_ms.toFixed(1)}ms
        {caseRun.cost_usd !== null && <> - ${caseRun.cost_usd.toFixed(4)}</>}
      </p>

      {caseRun.error && (
        <div className="alert alert-warn">
          <strong>{String(caseRun.error.type ?? "Error")}:</strong> {String(caseRun.error.message ?? "")}
        </div>
      )}

      <div className="card">
        <h2>Input</h2>
        <JsonBlock value={caseRun.case_input} />
        <h2>Expected</h2>
        <JsonBlock value={caseRun.case_expected} />
      </div>

      <div className="card">
        <h2>Output</h2>
        {caseRun.final_output && <p>{caseRun.final_output}</p>}
        <JsonBlock value={caseRun.structured_output} />
      </div>

      <div className="card">
        <h2>Evaluation results</h2>
        <table>
          <thead>
            <tr>
              <th>Dimension</th>
              <th>Evaluator</th>
              <th>Result</th>
              <th>Score</th>
              <th>Reasoning</th>
            </tr>
          </thead>
          <tbody>
            {caseRun.evaluation_results.map((result, i) => (
              <tr key={i}>
                <td>{result.dimension}</td>
                <td className="muted">
                  <code>{result.evaluator_key}</code> {result.evaluator_version}
                </td>
                <td>
                  <PassBadge passed={result.passed} />
                </td>
                <td>{result.score.toFixed(2)}</td>
                <td>{result.reasoning ?? <span className="muted">-</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Tool calls</h2>
        {caseRun.tool_calls.length === 0 ? (
          <p className="muted">No tool calls recorded.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Tool</th>
                <th>Status</th>
                <th>Latency (ms)</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {caseRun.tool_calls.map((tc) => (
                <tr key={tc.sequence_index}>
                  <td>{tc.sequence_index}</td>
                  <td>{tc.tool_name}</td>
                  <td>
                    <StatusBadge status={tc.status} />
                  </td>
                  <td>{tc.latency_ms?.toFixed(1) ?? "-"}</td>
                  <td>
                    <details>
                      <summary>arguments / result</summary>
                      <JsonBlock value={{ arguments: tc.arguments, result: tc.result }} />
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>Trace</h2>
        {caseRun.normalized_trace.length === 0 ? (
          <p className="muted">No trace recorded.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Step type</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {caseRun.normalized_trace.map((step, i) => (
                <tr key={i}>
                  <td className="muted">{step.timestamp ? new Date(step.timestamp).toLocaleTimeString() : "-"}</td>
                  <td>
                    <span className="badge badge-muted">{step.step_type}</span>
                  </td>
                  <td>
                    <details>
                      <summary>payload</summary>
                      <JsonBlock value={step.payload} />
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
