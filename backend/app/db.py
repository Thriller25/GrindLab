# backend/app/db.py

from pathlib import Path
from typing import Tuple

from app.core.settings import settings  # новый импорт
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker


def _normalize_db_url(raw_url: str) -> Tuple[str, str | None]:
    """
    Ensure sqlite URLs are absolute so we don't accidentally create multiple files
    when running commands from different working directories.
    """
    url = make_url(raw_url)
    resolved_path: str | None = None

    if url.drivername.startswith("sqlite"):
        db_path = url.database or "grindlab.db"
        path = Path(db_path)
        if not path.is_absolute():
            # repo root: backend/app/db.py -> ../.. is repo root
            base_dir = Path(__file__).resolve().parents[2]
            path = (base_dir / path).resolve()
        resolved_path = str(path)
        url = url.set(database=resolved_path)

    # render_as_string with hide_password=False to keep real password (str(url) masks it with ***)
    return url.render_as_string(hide_password=False), resolved_path


# Берём URL базы из настроек и фиксируем путь
DB_URL, SQLITE_PATH = _normalize_db_url(settings.db_url)

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

engine = create_engine(DB_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_path() -> str | None:
    """Return the resolved sqlite file path (if using sqlite)."""
    return SQLITE_PATH
