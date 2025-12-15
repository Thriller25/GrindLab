# backend/app/core/settings.py

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # URL базы данных для SQLAlchemy
    db_url: str = "sqlite:///./grindlab.db"

    # Флаг для включения debug-режима FastAPI (пока просто bool)
    app_debug: bool = True

    # Простое обозначение окружения
    environment: str = "dev"

    # Флаг тестового режима (можно переопределить переменной окружения TESTING=1)
    testing: bool = False

    # Вкл/выкл обязательной авторизации (для локальной разработки по умолчанию выключено)
    auth_enabled: bool = False

    # Настройки pydantic-settings (v2)
    model_config = SettingsConfigDict(
        env_file=".env",              # читаем переменные из .env
        env_file_encoding="utf-8",
        extra="ignore",               # игнорируем любые лишние переменные
    )


settings = Settings()

# Авто-определение тестового режима, если запущен pytest
if os.getenv("PYTEST_CURRENT_TEST"):
    settings.testing = True
