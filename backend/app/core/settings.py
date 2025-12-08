from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_url: str = "sqlite:///./grindlab.db"
    app_debug: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
