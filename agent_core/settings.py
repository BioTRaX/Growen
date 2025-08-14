import os

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        """Configuración basada en Pydantic para todo el proyecto."""

        env: str = "dev"
        db_url: str = "sqlite+aiosqlite:///./growen.db"
        pg_url: str = "postgresql+psycopg://user:pass@localhost:5432/growen"
        tn_client_id: str | None = None
        tn_client_secret: str | None = None
        tn_access_token: str | None = None
        tn_shop_id: str | None = None

        model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

except ModuleNotFoundError:

    class Settings:
        """Fallback simple cuando Pydantic no está disponible."""

        def __init__(self) -> None:
            self.env = os.getenv("ENV", "dev")
            self.db_url = os.getenv("DB_URL", "sqlite+aiosqlite:///./growen.db")
            self.pg_url = os.getenv(
                "PG_URL", "postgresql+psycopg://user:pass@localhost:5432/growen"
            )
            self.tn_client_id = os.getenv("TN_CLIENT_ID")
            self.tn_client_secret = os.getenv("TN_CLIENT_SECRET")
            self.tn_access_token = os.getenv("TN_ACCESS_TOKEN")
            self.tn_shop_id = os.getenv("TN_SHOP_ID")


settings = Settings()
