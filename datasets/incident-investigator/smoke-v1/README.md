# incident-investigator-smoke-v1

The real-adapter counterpart to `datasets/stub-agent/smoke-v1` (docs/roadmap.md Phase 2):
3 cases run against the actual AI Operations Center
(github.com/fegbewunmi/ai-operations-center) through `IncidentInvestigatorAdapter`
(`backend/app/adapters/incident_investigator/`).

Each case replays one of that system's own committed eval fixtures
(`backend/eval/fixtures/{INC-FD-001,INC-LR-001,INC-RL-001}.json`) via
`POST /v1/investigations/replay/{fixture_id}` - deterministic evidence (telemetry,
deployment records, knowledge base), non-deterministic reasoning (a real Gemini call per
node, same as production). `expected` values are copied from each fixture's own
`ground_truth` block, not invented independently, so this dataset stays honest about what
that system's own authors consider correct for these scenarios.

Running this dataset costs real Gemini API calls (~$0.001–0.002 per case, per the target
system's own token accounting) and takes roughly 1–2 minutes per case. It requires:
- the AI Operations Center backend running locally (`uvicorn app.main:app --port 8080`)
- its Cloud SQL instance reachable (`cloud-sql-proxy ... --port 5433`)
- valid GCP Application Default Credentials with Vertex AI access

This is deliberately a small (3-case) dataset: there are only 3 fixtures currently
committed upstream. Extend it if that repo adds more.
