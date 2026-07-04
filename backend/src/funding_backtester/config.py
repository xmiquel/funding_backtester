"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "funding_backtester"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/funding_backtester"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]
    duckdb_path: str = "data/ticks.duckdb"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
