import os

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        """Configuración basada en Pydantic."""

        env: str = "dev"
        db_url_postgres: str = "postgresql+psycopg://user:pass@localhost:5432/growen"
        db_url_sqlite: str = "sqlite:///./growen.db"
        use_sqlite: bool = True

        model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

        @property
        def db_url(self) -> str:
            return self.db_url_sqlite if self.use_sqlite else self.db_url_postgres

except ModuleNotFoundError:
    class Settings:
        """Fallback simple cuando Pydantic no está disponible."""

        def __init__(self) -> None:
            self.env = os.getenv("ENV", "dev")
            self.db_url_postgres = os.getenv(
                "DB_URL_POSTGRES", "postgresql+psycopg://user:pass@localhost:5432/growen"
            )
            self.db_url_sqlite = os.getenv("DB_URL_SQLITE", "sqlite:///./growen.db")
            self.use_sqlite = os.getenv("USE_SQLITE", "1") == "1"

        @property
        def db_url(self) -> str:
            return self.db_url_sqlite if self.use_sqlite else self.db_url_postgres


settings = Settings()
