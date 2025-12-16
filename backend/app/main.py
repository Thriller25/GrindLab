from fastapi import FastAPI

from app.db import Base, engine
from app.routers import (
    api_router,
    calc,
    calc_runs,
    calc_scenarios,
    calc_comparisons,
    comments,
    me,
    projects,
    auth,
)


app = FastAPI(title="GrindLab Backend", version="0.1.0")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    """
    Dev-only DB initialization: create all tables in SQLite if they do not exist yet.
    """
    import app.models  # noqa: F401 - ensure models are imported for metadata

    Base.metadata.create_all(bind=engine)


app.include_router(api_router, prefix="/api")
app.include_router(calc.router)
app.include_router(calc_runs.router)
app.include_router(calc_scenarios.router)
app.include_router(calc_comparisons.router)
app.include_router(comments.router)
app.include_router(comments.me_router)
app.include_router(me.router)
app.include_router(projects.router)
app.include_router(auth.router)
