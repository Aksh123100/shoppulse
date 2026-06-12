from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/shoppulse"
    ANTHROPIC_API_KEY: str = ""
    CHANNEL_STUB_URL: str = "http://localhost:8001"
    CRM_CALLBACK_URL: str = "http://localhost:8000"
    SECRET_KEY: str = "shoppulse-secret-key-2026"

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
