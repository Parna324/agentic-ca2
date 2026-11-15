"""Configuration management using pydantic-settings."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: Optional[str] = None
    offline_mode: bool = True
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    database_url: str = "sqlite:///./code_review.db"
    secret_key: str = "change-me-in-production"
    max_file_size_mb: int = 10
    max_findings_per_agent: int = 50
    critical_threshold: int = 1
    high_security_threshold: int = 1
    next_public_api_url: str = "http://localhost:8000"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
