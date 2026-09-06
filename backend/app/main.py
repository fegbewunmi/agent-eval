"""FastAPI app entrypoint. Wraps the runner and comparison service (Phase 2), the
LLM-judge evaluator (Phase 3), and read-only catalog browsing for the frontend (Phase 4).
No create/update/delete endpoints for Agent/Dataset/Evaluator — those are still
registered via app/services/seed.py and scripts/load_dataset.py, per ADR-0003 and
docs/phase-notes/phase-2.md's explicit deferral of a full CRUD API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.catalog import router as catalog_router
from app.api.runs import router as runs_router

app = FastAPI(title="Agent Evaluation Platform", version="0.1.0")
app.include_router(runs_router)
app.include_router(catalog_router)

# The Next.js frontend (Phase 4) runs on a different origin in dev (localhost:3000) than
# this API (localhost:8000/8080/...) — this is an internal tool with no auth yet
# (docs/product-overview.md), so a permissive localhost allowlist is proportionate; revisit
# if this is ever deployed somewhere with real origins to restrict to.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["ops"])
def health() -> dict:
    return {"status": "ok"}
