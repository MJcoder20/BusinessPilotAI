from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    app_env: Literal["development", "production"] = "development"
    frontend_origin: str = "http://localhost:5173"

    # API rate limiting.
    ai_chat_rate_limit: str = "10/minute"
    ai_stream_rate_limit: str = "5/minute"
    # Local development database URL.
    database_url: str | None = None

    # Docker database secret configuration.
    db_password_file: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_name: str = "businesspilot_db"

    # Database connection pool.
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30

    # LangGraph checkpoint connection pool.
    checkpoint_pool_min_size: int = 1
    checkpoint_pool_max_size: int = 2

    # AI model configuration.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"

    # AI model provider configuration.
    chat_model_provider: Literal["ollama", "gemini"] = "ollama"

    # Google Gemini configuration.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Authentication and JWT configuration.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7


    @property
    def resolved_database_url(self) -> str:
        """Resolve the database URL from local configuration or Docker secret."""

        if self.db_password_file:
            password = Path(self.db_password_file).read_text(
                encoding="utf-8"
            ).rstrip("\r\n")

            return URL.create(
                drivername="postgresql+psycopg",
                username=self.db_user,
                password=password,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
            ).render_as_string(hide_password=False)

        if self.database_url:
            return self.database_url

        raise ValueError(
            "Database configuration is missing. "
            "Set DATABASE_URL or DB_PASSWORD_FILE."
        )


settings = Settings()
