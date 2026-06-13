from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/shoppulse"
    ANTHROPIC_API_KEY: str = ""   # kept for reference, not used in Day 2
    GEMINI_API_KEY: str = ""      # NEW: get free key at aistudio.google.com/app/apikey
    CHANNEL_STUB_URL: str = "http://localhost:8001"
    CRM_CALLBACK_URL: str = "http://localhost:8000"
    SECRET_KEY: str = "shoppulse-secret-key-2026"

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()