# backend/app/core/settings.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # URL базы данных для SQLAlchemy
    db_url: str = "sqlite:///./grindlab.db"

    # Флаг для включения debug-режима FastAPI (пока просто bool)
    app_debug: bool = True

    # Настройки pydantic-settings (v2)
    model_config = SettingsConfigDict(
        env_file=".env",              # читаем переменные из .env
        env_file_encoding="utf-8",
        extra="ignore",               # игнорируем любые лишние переменные
    )


settings = Settings()
