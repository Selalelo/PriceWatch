"""
config.py  —  Centralised settings
"""

from pathlib import Path
from pydantic_settings import BaseSettings

ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Groq
    groq_api_key: str

    # App — used for email redirect URLs
    app_url: str = "https://effective-trout-qr746q4r97536wjg-8000.app.github.dev"

    # App env
    app_env: str = "development"

    model_config = {
        "env_file": str(ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()