import logging
import os
from contextlib import asynccontextmanager

from app.core.rate_limit import limiter
from app.core.settings import settings
from app.db import Base, engine, get_db_path
from app.routers import (
    api_router,
    auth,
    calc,
    calc_comparisons,
    calc_runs,
    calc_scenarios,
    comments,
    favorites,
    me,
    projects,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    import app.models  # noqa: F401 - ensure models are imported for metadata

    logger.info("DB url (settings.db_url): %s", settings.db_url)
    logger.info("DB engine url: %s", engine.url)
    db_path = get_db_path()
    if db_path:
        logger.info("DB sqlite file path: %s", db_path)
        logger.info("[GrindLab] Using sqlite DB at: %s", db_path)
    else:
        logger.info("[GrindLab] Using database URL: %s", engine.url)
    Base.metadata.create_all(bind=engine)

    yield  # Application is running

    # Shutdown (cleanup if needed)


app = FastAPI(title="GrindLab Backend", version="0.1.0", lifespan=lifespan)

logger = logging.getLogger("uvicorn.error")

# ============================================================================
# CORS Middleware Configuration
# ============================================================================
# Разрешенные origins из переменной окружения или по умолчанию localhost
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(
    ","
)

# Разрешенные HTTP методы (явно)
ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]

# Разрешенные заголовки (явно)
ALLOWED_HEADERS = ["Content-Type", "Authorization", "Accept", "Origin"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=ALLOWED_METHODS,
    allow_headers=ALLOWED_HEADERS,
)

# ============================================================================
# Rate Limiting Middleware (SlowAPI)
# ============================================================================
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    """Обработчик ошибок rate limiting"""
    return {
        "detail": f"Rate limit exceeded. {exc.detail}",
        "status_code": 429,
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(api_router, prefix="/api")
app.include_router(calc.router)
app.include_router(calc_runs.router)
app.include_router(calc_scenarios.router)
app.include_router(calc_comparisons.router)
app.include_router(comments.router)
app.include_router(me.router)
app.include_router(favorites.router)
app.include_router(projects.router)
app.include_router(auth.router)
