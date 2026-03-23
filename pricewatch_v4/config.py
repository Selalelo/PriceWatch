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
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Groq
    groq_api_key: str

    # App — used for email redirect URLs
    app_url: str = "https://pricewatch-br8y.onrender.com"

    # App env
    app_env: str = "development"

    model_config = {
        "env_file": str(ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()