"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

KlineInterval = Literal["1m", "3m", "5m", "15m", "1h"]
KLINE_INTERVAL_CHOICES: tuple[str, ...] = ("1m", "3m", "5m", "15m", "1h")


class Settings(BaseSettings):
    """Runtime settings for the crypto prediction pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenRouter / Hermes
    openrouter_api_key: str = Field(
        ...,
        description="API key for OpenRouter (also used by Hermes Agent).",
    )
    llm_model: str = Field(
        default="google/gemma-2-9b-it:free",
        description="OpenRouter model id (prefer a :free tier model for development).",
    )
    llm_fallback_models: tuple[str, ...] = Field(
        default=("meta-llama/llama-3.1-8b-instruct:free", "mistralai/mistral-7b-instruct:free"),
        description="Fallback OpenRouter models tried when the primary model fails.",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter REST API base URL.",
    )
    app_name: str = Field(
        default="CrowdWisdomTrading-Prediction-Agent",
        description="Used in OpenRouter attribution headers.",
    )

    # Binance public API (no key required for klines)
    binance_base_url: str = Field(
        default="https://api.binance.com",
        description="Binance REST API base URL.",
    )
    kline_interval: KlineInterval = Field(
        default="5m",
        description="Candle interval for features and prediction horizon alignment.",
    )
    kline_limit: int = Field(
        default=1000,
        ge=10,
        le=1000,
        description="Number of recent candles to fetch per symbol.",
    )

    symbols: tuple[str, ...] = Field(
        default=("BTCUSDT", "ETHUSDT"),
        description="Binance spot symbols to track.",
    )

    # Risk
    kelly_fraction: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Fractional Kelly scaler (quarter Kelly is common).",
    )
    max_kelly_stake: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Hard cap on suggested stake as fraction of bankroll.",
    )

    # Feedback persistence
    feedback_store_path: str = Field(
        default="data/feedback.json",
        description="JSON ledger for predictions, outcomes, and rolling accuracy.",
    )

    log_level: str = Field(default="INFO")

    log_file_path: str | None = Field(
        default=None,
        description="If set, duplicate logs to this file path.",
    )

    # Apify
    apify_token: str | None = Field(
        default=None,
        description="Apify API token for actor runs.",
    )
    apify_polymarket_actor_id: str | None = Field(
        default=None,
        description="Apify actor id for Polymarket scraping.",
    )
    apify_kalshi_actor_id: str | None = Field(
        default=None,
        description="Apify actor id for Kalshi scraping.",
    )
    apify_timeout_s: float = Field(default=45.0, ge=5.0, le=240.0)
    enable_apify: bool = Field(
        default=True,
        description="Enable Apify market scraping.",
    )

    # Prediction
    enable_kronos: bool = Field(
        default=True,
        description="Attempt Kronos prediction path before fallback logic.",
    )
    kronos_repo_path: str | None = Field(
        default=None,
        description="Optional local filesystem path to a Kronos repository checkout.",
    )
    enable_llm_reasoning: bool = Field(
        default=True,
        description="Use OpenRouter to generate rationale sanity-check text.",
    )

    # Hermes runtime behavior
    strict_integrations: bool = Field(
        default=False,
        description="When true, fail pipeline if external integration is unavailable.",
    )

    @field_validator("symbols", mode="before")
    @classmethod
    def _parse_symbols(cls, v: object) -> tuple[str, ...]:
        if v is None:
            return ("BTCUSDT", "ETHUSDT")
        if isinstance(v, str):
            parts = [s.strip().upper() for s in v.split(",") if s.strip()]
            return tuple(parts) if parts else ("BTCUSDT", "ETHUSDT")
        if isinstance(v, (list, tuple)):
            return tuple(str(s).strip().upper() for s in v)
        return v  # type: ignore[return-value]

    @field_validator("llm_fallback_models", mode="before")
    @classmethod
    def _parse_llm_fallback_models(cls, v: object) -> tuple[str, ...]:
        if v is None:
            return ("meta-llama/llama-3.1-8b-instruct:free", "mistralai/mistral-7b-instruct:free")
        if isinstance(v, str):
            parts = [s.strip() for s in v.split(",") if s.strip()]
            return tuple(parts)
        if isinstance(v, (list, tuple)):
            return tuple(str(s).strip() for s in v if str(s).strip())
        return tuple()


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance (suitable for import-time use in workers)."""
    return Settings()
