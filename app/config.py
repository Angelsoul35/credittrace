"""Application configuration, loaded from environment variables (prefix ``CT_``)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CT_", env_file=".env", extra="ignore")

    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./credittrace.db"

    model_dir: str = "ml/artifacts"
    model_version: str = ""

    chain_enabled: bool = True
    chain_rpc_url: str = "http://anvil:8545"
    contract_address: str = ""
    chain_private_key: str = ""

    # Probability-of-default thresholds in basis points (1% = 100 bps).
    band_low_max_bps: int = 1500
    band_medium_max_bps: int = 4000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
