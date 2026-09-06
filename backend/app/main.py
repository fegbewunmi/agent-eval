"""FastAPI app entrypoint. docs/roadmap.md Phase 2 — wraps the runner and comparison
service; no CRUD endpoints for Agent/Dataset/Evaluator yet (still registered via
app/services/seed.py, e.g. from scripts/run_eval.py). See docs/phase-notes/phase-2.md.
"""

from fastapi import FastAPI

from app.api.runs import router as runs_router

app = FastAPI(title="Agent Evaluation Platform", version="0.1.0")
app.include_router(runs_router)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok"}
