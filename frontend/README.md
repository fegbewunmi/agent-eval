# Frontend

Next.js (App Router) + TypeScript frontend for the Agent Evaluation Platform. See
`../docs/` for architecture and design docs, and `../docs/phase-notes/phase-4.md` for what
this app does and why it's built the way it is; this file is just setup/run instructions.

No client components, no state-management library, no CSS framework - every page is a
Server Component fetching directly from the backend API, and both mutating flows (trigger
a run, pick two runs to compare) use plain HTML forms.

## Setup

Requires the backend API running (see `../backend/README.md`) - by default at
`http://localhost:8000`.

```bash
cd frontend
npm install
cp .env.local.example .env.local   # edit AGENT_EVAL_API_URL if the backend runs elsewhere
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Pages

- `/` - recent runs.
- `/agents`, `/datasets`, `/datasets/[id]` - read-only catalog browsing.
- `/runs/new` - trigger a run (agent version, dataset, evaluators).
- `/runs/[id]` - run summary, optionally filtered by `?tag=`.
- `/runs/[id]/cases/[caseRunId]` - full case detail: input, expected, output, trace, tool
  calls, evaluation results.
- `/runs/compare` - pick two runs; regressions surfaced before aggregate stats.

## Build

```bash
npm run build
```
