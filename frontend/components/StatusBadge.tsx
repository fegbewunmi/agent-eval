const STATUS_CLASS: Record<string, string> = {
  completed: "badge badge-pass",
  success: "badge badge-pass",
  completed_with_errors: "badge badge-warn",
  timeout: "badge badge-warn",
  failed: "badge badge-fail",
  error: "badge badge-fail",
  pending: "badge badge-muted",
  running: "badge badge-muted",
};

export function StatusBadge({ status }: { status: string }) {
  const className = STATUS_CLASS[status] ?? "badge badge-muted";
  return <span className={className}>{status.replace(/_/g, " ")}</span>;
}
