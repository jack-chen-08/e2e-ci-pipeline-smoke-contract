"""Runtime configuration — every value comes from the environment, nothing is inlined."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@127.0.0.1:55432/app"
    redis_url: str = "redis://127.0.0.1:56379/0"
    external_stub_url: str = "http://127.0.0.1:8081"

    # The nightly failure summary posts here. In CI it comes from a repository secret;
    # the drill uses the local stub that ships with the repo.
    wecom_webhook: str = ""
    report_base_url: str = ""


settings = Settings()
