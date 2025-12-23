import os
from contextlib import asynccontextmanager

from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware
from app.core.rate_limit import limiter
from app.core.settings import settings
from app.db import Base, engine, get_db, get_db_path
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
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

# Configure structured logging at module load
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    import app.models  # noqa: F401 - ensure models are imported for metadata

    logger.info("application_starting", db_url=str(settings.db_url))
    db_path = get_db_path()
    if db_path:
        logger.info("using_sqlite_database", path=db_path)
    else:
        logger.info("using_database", url=str(engine.url))
    Base.metadata.create_all(bind=engine)
    logger.info("database_tables_created")

    yield  # Application is running

    # Shutdown
    logger.info("application_shutdown")


app = FastAPI(title="GrindLab Backend", version="0.1.0", lifespan=lifespan)

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

# ============================================================================
# Request Logging Middleware (must be added after other middleware)
# ============================================================================
app.add_middleware(RequestLoggingMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    """Обработчик ошибок rate limiting"""
    return {
        "detail": f"Rate limit exceeded. {exc.detail}",
        "status_code": 429,
    }


@app.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "service": "grindlab-backend"}


@app.get("/health/ready")
def readiness_check(db=Depends(get_db)):
    """
    Readiness check - verifies database connectivity.
    Used by container orchestration for readiness probes.
    """
    try:
        # Simple query to verify DB connection
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        return {"status": "not_ready", "database": "disconnected", "error": str(e)}


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
