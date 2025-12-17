import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.db import Base, engine, get_db_path
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

logger = logging.getLogger("uvicorn.error")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    """
    Dev-only DB initialization: create all tables in SQLite if they do not exist yet.
    """
    import app.models  # noqa: F401 - ensure models are imported for metadata
    logger.info("DB url (settings.db_url): %s", settings.db_url)
    logger.info("DB engine url: %s", engine.url)
    db_path = get_db_path()
    if db_path:
        logger.info("DB sqlite file path: %s", db_path)
        print(f"[GrindLab] Using sqlite DB at: {db_path}")
    else:
        print(f"[GrindLab] Using database URL: {engine.url}")
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
