from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    usda_api_key: str | None = None
    usda_base_url: str = "https://api.nal.usda.gov/fdc/v1"
    off_base_url: str = "https://world.openfoodfacts.org"
    db_path: str = "data/scm.db"
    http_timeout: float = 8.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
