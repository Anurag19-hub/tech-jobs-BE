
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IndiaTechIntelligence API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    supabase_url: str
    supabase_key: str

    # Set COLLECTION_API_KEY in backend/.env.
    # An empty value disables collection endpoint access.
    collection_api_key: str = ""

    frontend_origins: str = (
        "http://localhost:3000,http://localhost:5173"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.frontend_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
