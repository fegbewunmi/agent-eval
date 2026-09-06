import Link from "next/link";
import { listDatasets } from "@/lib/api";

export default async function DatasetsPage() {
  const datasets = await listDatasets();

  return (
    <section>
      <h1>Datasets</h1>
      <p className="muted">
        Authored as files and loaded via <code>scripts/load_dataset.py</code> (ADR-0003) - see{" "}
        <code>docs/dataset-authoring.md</code>. No create form here; edit the dataset&apos;s
        <code>cases.yaml</code> and reload it.
      </p>

      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Description</th>
            <th>Cases</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {datasets.map((dataset) => (
            <tr key={dataset.id}>
              <td>{dataset.name}</td>
              <td className="muted">{dataset.description ?? "-"}</td>
              <td>{dataset.case_count}</td>
              <td>
                <Link href={`/datasets/${dataset.id}`}>View cases</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
