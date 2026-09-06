import { listAgents } from "@/lib/api";

export default async function AgentsPage() {
  const agents = await listAgents();

  return (
    <section>
      <h1>Agents</h1>
      <p className="muted">
        Registered via <code>app/services/seed.py</code> (see <code>backend/README.md</code>) - no
        create form here yet, consistent with docs/phase-notes/phase-2.md&apos;s deferral of a full CRUD API.
      </p>

      {agents.length === 0 && <p className="muted">No agents registered yet.</p>}

      {agents.map((agent) => (
        <div key={agent.id} className="card">
          <h2>{agent.name}</h2>
          <p className="muted">
            adapter key: <code>{agent.adapter_key}</code>
          </p>
          {agent.description && <p>{agent.description}</p>}

          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Description</th>
                <th>Registered</th>
              </tr>
            </thead>
            <tbody>
              {agent.versions.map((version) => (
                <tr key={version.id}>
                  <td>
                    <code>{version.version_label}</code>
                  </td>
                  <td>{version.description ?? "-"}</td>
                  <td className="muted">{new Date(version.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </section>
  );
}
