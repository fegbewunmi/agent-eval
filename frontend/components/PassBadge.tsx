// Distinguishes "failed" from "not applicable" (docs/evaluation-methodology.md) - a null
// passed value is not a failure, and rendering it identically to one would repeat the
// exact reporting bug fixed in docs/phase-notes/phase-2.md.
export function PassBadge({ passed }: { passed: boolean | null }) {
  if (passed === null) return <span className="badge badge-muted">n/a</span>;
  return passed ? <span className="badge badge-pass">pass</span> : <span className="badge badge-fail">fail</span>;
}
