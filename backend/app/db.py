import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Для разработки используем SQLite
DB_URL = os.getenv("GRINDLAB_DB_URL", "sqlite:///./grindlab.db")

engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ВАЖНО: импорт моделей после объявления Base,
# чтобы metadata знала про все таблицы
from app import models  # noqa: E402,F401  - импорт оставляем в конце файла

# Создаём таблицы в БД, если их ещё нет
Base.metadata.create_all(bind=engine)
