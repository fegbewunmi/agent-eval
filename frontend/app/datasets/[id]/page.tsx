import { getDataset } from "@/lib/api";

export default async function DatasetDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const dataset = await getDataset(id);

  return (
    <section>
      <h1>{dataset.name}</h1>
      {dataset.description && <p className="muted">{dataset.description}</p>}

      <table>
        <thead>
          <tr>
            <th>Case key</th>
            <th>Tags</th>
          </tr>
        </thead>
        <tbody>
          {dataset.cases.map((c) => (
            <tr key={c.id}>
              <td>
                <code>{c.key}</code>
              </td>
              <td>
                {c.tags.length === 0 ? (
                  <span className="muted">-</span>
                ) : (
                  c.tags.map((tag) => (
                    <span key={tag} className="tag-chip">
                      {tag}
                    </span>
                  ))
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
