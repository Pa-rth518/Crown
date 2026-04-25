"""Binance public REST client for OHLCV klines."""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.binance.com"
BINANCE_KLINE_MAX_LIMIT = 1000


def _row_to_candle(row: list[Any], symbol: str) -> dict[str, Any] | None:
    """Map one Binance kline array to a structured dict; return None if malformed."""
    if not isinstance(row, list) or len(row) < 11:
        log.warning("Skipping malformed kline row for %s (len=%s)", symbol, len(row) if isinstance(row, list) else "n/a")
        return None
    try:
        return {
            "symbol": symbol.upper(),
            "open_time": int(row[0]),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
            "close_time": int(row[6]),
            "quote_volume": float(row[7]),
            "trades": int(row[8]),
            "taker_buy_base": float(row[9]),
            "taker_buy_quote": float(row[10]),
        }
    except (TypeError, ValueError) as exc:
        log.warning("Skipping kline row for %s: conversion failed: %s", symbol, exc)
        return None


def _request_klines_raw(
    *,
    base_url: str,
    symbol: str,
    interval: str,
    limit: int,
    timeout_s: float,
) -> list[list[Any]]:
    """Perform HTTP GET and return Binance-native list-of-lists."""
    sym = symbol.strip().upper()
    if not sym:
        raise ValueError("symbol must be non-empty")

    if not 1 <= limit <= BINANCE_KLINE_MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {BINANCE_KLINE_MAX_LIMIT}, got {limit}")

    url = f"{base_url.rstrip('/')}/api/v3/klines"
    params = {"symbol": sym, "interval": interval, "limit": limit}

    try:
        with httpx.Client(timeout=timeout_s) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        log.error("Binance klines timeout for %s interval=%s limit=%s: %s", sym, interval, limit, exc)
        raise
    except httpx.HTTPStatusError as exc:
        log.error(
            "Binance klines HTTP error for %s: status=%s body=%s",
            sym,
            exc.response.status_code,
            exc.response.text[:500] if exc.response else "",
        )
        raise
    except httpx.RequestError as exc:
        log.error("Binance klines request failed for %s: %s", sym, exc)
        raise

    if isinstance(data, dict) and "code" in data:
        msg = data.get("msg", data)
        log.error("Binance API error for %s: %s", sym, msg)
        raise RuntimeError(f"Binance API error for {sym}: {msg}")

    if not isinstance(data, list):
        log.error("Unexpected klines payload type for %s: %s", sym, type(data))
        raise ValueError(f"Unexpected klines payload type: {type(data)}")

    log.info("Fetched %s raw klines for %s interval=%s limit=%s", len(data), sym, interval, limit)
    return data


def get_klines(
    symbol: str,
    interval: str = "1m",
    limit: int = 1000,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout_s: float = 30.0,
) -> list[dict[str, Any]]:
    """
    Fetch candlesticks from Binance spot public API.

    Parameters
    ----------
    symbol
        Trading pair, e.g. ``BTCUSDT`` or ``ETHUSDT``.
    interval
        Kline interval (e.g. ``1m``, ``5m``).
    limit
        Number of candles (max 1000 per Binance).
    base_url
        REST base URL (default mainnet spot).
    timeout_s
        HTTP client timeout in seconds.

    Returns
    -------
    list[dict[str, Any]]
        Newest candles last (Binance default order). Each dict has OHLCV and metadata fields.

    Raises
    ------
    ValueError
        Invalid ``symbol`` or ``limit``.
    RuntimeError
        Binance returned an error object in JSON.
    httpx.HTTPError
        Network / HTTP failures after logging.
    """
    sym = symbol.strip().upper()
    raw_rows = _request_klines_raw(
        base_url=base_url,
        symbol=sym,
        interval=interval,
        limit=limit,
        timeout_s=timeout_s,
    )

    candles: list[dict[str, Any]] = []
    for row in raw_rows:
        candle = _row_to_candle(row, sym)
        if candle is not None:
            candles.append(candle)

    if len(candles) != len(raw_rows):
        log.warning(
            "Normalized %s/%s candles for %s (dropped %s bad rows)",
            len(candles),
            len(raw_rows),
            sym,
            len(raw_rows) - len(candles),
        )

    return candles


class BinanceClient:
    """Fetches candlestick data from Binance spot API (no authentication)."""

    def __init__(self, base_url: str, timeout_s: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_s

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        limit: int,
    ) -> list[list[Any]]:
        """
        Return raw klines as returned by Binance (list of lists).

        Each row: [open_time, open, high, low, close, volume, ...]
        """
        return _request_klines_raw(
            base_url=self._base_url,
            symbol=symbol,
            interval=interval,
            limit=limit,
            timeout_s=self._timeout,
        )
