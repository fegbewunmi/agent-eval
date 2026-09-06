export function JsonBlock({ value }: { value: unknown }) {
  if (value === null || value === undefined) return <span className="muted">-</span>;
  return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>;
}
