# tests/conftest.py

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Добавляем корень backend в PYTHONPATH, чтобы импортировался пакет app
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.rate_limit import limiter  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    """
    Перед каждым тестом пересоздаём структуру БД,
    чтобы тесты не влияли друг на друга.
    Также сбрасываем rate limiter, чтобы лимиты не накапливались между тестами.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # Сброс rate limiter storage для изоляции тестов
    limiter.reset()
    yield
    # после теста можно не дропать — всё равно пересоздадим перед следующим


@pytest.fixture()
def client() -> TestClient:
    """
    Фикстура HTTP-клиента для тестирования FastAPI-приложения.
    """
    with TestClient(app) as c:
        yield c
