"""Market source loaders for Polymarket and Kalshi."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from services.apify_client import ApifyClient

log = logging.getLogger(__name__)


def fetch_polymarket_rows(
    *,
    apify: ApifyClient | None,
    apify_actor_id: str | None,
) -> list[dict[str, Any]]:
    if apify and apify_actor_id:
        try:
            items = apify.run_actor_and_get_items(
                actor_id=apify_actor_id,
                actor_input={"category": "crypto"},
                max_items=30,
            )
            normalized = [_normalize_polymarket(i) for i in items]
            return [r for r in normalized if r]
        except Exception as exc:
            log.warning("Apify Polymarket fetch failed: %s", exc)

    url = "https://gamma-api.polymarket.com/markets"
    params = {"closed": "false", "limit": 40}
    try:
        with httpx.Client(timeout=20.0) as client:
            res = client.get(url, params=params)
            res.raise_for_status()
            payload = res.json()
    except Exception as exc:
        log.warning("Polymarket API fetch failed: %s", exc)
        return []
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        row = _normalize_polymarket(item)
        if row:
            rows.append(row)
    return rows


def fetch_kalshi_rows(*, apify: ApifyClient | None, apify_actor_id: str | None) -> list[dict[str, Any]]:
    if apify and apify_actor_id:
        try:
            items = apify.run_actor_and_get_items(
                actor_id=apify_actor_id,
                actor_input={"category": "crypto"},
                max_items=30,
            )
            normalized = [_normalize_kalshi(i) for i in items]
            return [r for r in normalized if r]
        except Exception as exc:
            log.warning("Apify Kalshi fetch failed: %s", exc)

    url = "https://api.elections.kalshi.com/trade-api/v2/markets"
    params = {"status": "open", "limit": 100}
    try:
        with httpx.Client(timeout=20.0) as client:
            res = client.get(url, params=params)
            res.raise_for_status()
            payload = res.json()
    except Exception as exc:
        log.warning("Kalshi API fetch failed: %s", exc)
        return []

    markets = payload.get("markets", []) if isinstance(payload, dict) else []
    rows: list[dict[str, Any]] = []
    for item in markets:
        if not isinstance(item, dict):
            continue
        row = _normalize_kalshi(item)
        if row:
            rows.append(row)
    return rows


def _detect_asset(text: str) -> str | None:
    t = text.upper()
    if "BTC" in t or "BITCOIN" in t:
        return "BTC"
    if "ETH" in t or "ETHEREUM" in t:
        return "ETH"
    return None


def _normalize_polymarket(item: dict[str, Any]) -> dict[str, Any] | None:
    question = str(item.get("question") or item.get("title") or "")
    asset = _detect_asset(question)
    if asset is None:
        return None
    return {
        "source": "polymarket",
        "market_id": item.get("id") or item.get("market_id"),
        "question": question,
        "asset": asset,
        "category": "crypto",
        "raw": item,
    }


def _normalize_kalshi(item: dict[str, Any]) -> dict[str, Any] | None:
    title = str(item.get("title") or item.get("subtitle") or item.get("ticker") or "")
    asset = _detect_asset(title)
    if asset is None:
        return None
    return {
        "source": "kalshi",
        "ticker": item.get("ticker"),
        "title": title,
        "asset": asset,
        "category": "crypto",
        "raw": item,
    }
