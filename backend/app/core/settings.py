from pydantic import BaseSettings


class Settings(BaseSettings):
    DB_URL: str = "sqlite:///./grindlab.db"
    APP_DEBUG: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
