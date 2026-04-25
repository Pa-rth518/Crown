"""Market data agent: fetches cleaned OHLCV via Binance (Hermes-style agent contract)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from agents.exceptions import AgentError
from config import Settings
from services.binance_client import get_klines

log = logging.getLogger(__name__)

AssetSymbol = Literal["BTC", "ETH"]


def _binance_pair(asset: AssetSymbol) -> str:
    """Map logical asset to Binance spot symbol."""
    return f"{asset}USDT"


def resolve_asset_symbol(binance_or_short: str) -> AssetSymbol | None:
    """
    Parse ``BTCUSDT`` / ``btc`` style strings into ``BTC`` or ``ETH``.

    Returns ``None`` if the pair is not supported by this agent.
    """
    raw = binance_or_short.strip().upper()
    if raw.endswith("USDT"):
        raw = raw[: -len("USDT")]
    if raw == "BTC":
        return "BTC"
    if raw == "ETH":
        return "ETH"
    return None


@dataclass(frozen=True)
class DataAgentInput:
    """Single-asset request."""

    asset: AssetSymbol
    interval: str | None = None
    """If None, uses ``Settings.kline_interval``."""

    limit: int | None = None
    """If None, uses ``Settings.kline_limit`` (capped at Binance max 1000)."""


@dataclass(frozen=True)
class DataAgentOutput:
    """Cleaned candle rows (list of dicts from ``get_klines``)."""

    asset: AssetSymbol
    binance_symbol: str
    interval: str
    candles: tuple[dict[str, Any], ...]
    """Chronological OHLCV rows (oldest first, newest last)."""


class DataAgent:
    """
    Data plane agent: same shape as other agents (settings + ``run(input) -> output``).

    Uses ``services.binance_client.get_klines`` only; no LLM. Pairs with Hermes-driven
    agents (e.g. ``SearchAgent``) in the orchestration layer.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(self, inp: DataAgentInput) -> DataAgentOutput:
        interval = inp.interval if inp.interval is not None else self._settings.kline_interval
        limit = inp.limit if inp.limit is not None else min(self._settings.kline_limit, 1000)

        pair = _binance_pair(inp.asset)
        log.info(
            "DataAgent fetching %s (%s) interval=%s limit=%s",
            inp.asset,
            pair,
            interval,
            limit,
        )

        try:
            rows = get_klines(
                pair,
                interval=interval,
                limit=limit,
                base_url=self._settings.binance_base_url,
            )
        except Exception as exc:
            log.exception("DataAgent failed for %s (%s)", inp.asset, pair)
            raise AgentError("DataAgent", f"Binance fetch failed for {pair}") from exc

        log.info("DataAgent loaded %s candles for %s", len(rows), pair)
        return DataAgentOutput(
            asset=inp.asset,
            binance_symbol=pair,
            interval=interval,
            candles=tuple(rows),
        )
