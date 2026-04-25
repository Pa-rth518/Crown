"""Discover tradable crypto assets and prediction-market context."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from agents.data_agent import AssetSymbol
from agents.exceptions import AgentError
from config import Settings
from services.apify_client import ApifyClient
from services.market_sources import fetch_kalshi_rows, fetch_polymarket_rows

log = logging.getLogger(__name__)

def simulate_polymarket_crypto_markets() -> list[dict[str, Any]]:
    """Placeholder Polymarket-style rows (no network I/O)."""
    return [
        {
            "source": "polymarket",
            "market_id": "sim-pm-btc-001",
            "question": "Simulated: BTC higher over next 24h?",
            "category": "crypto",
            "asset": "BTC",
            "volume_usd_sim": 182_000.0,
        },
        {
            "source": "polymarket",
            "market_id": "sim-pm-eth-001",
            "question": "Simulated: ETH higher over next 24h?",
            "category": "crypto",
            "asset": "ETH",
            "volume_usd_sim": 96_000.0,
        },
    ]


def simulate_kalshi_crypto_markets() -> list[dict[str, Any]]:
    """Placeholder Kalshi-style rows (no network I/O)."""
    return [
        {
            "source": "kalshi",
            "ticker": "SIMKX-BTC-24H",
            "title": "Simulated Kalshi series: BTC daily direction",
            "category": "crypto",
            "asset": "BTC",
            "open_interest_sim": 4_200,
        },
        {
            "source": "kalshi",
            "ticker": "SIMKX-ETH-24H",
            "title": "Simulated Kalshi series: ETH daily direction",
            "category": "crypto",
            "asset": "ETH",
            "open_interest_sim": 2_800,
        },
    ]


@dataclass(frozen=True)
class SearchAgentInput:
    """Optional hints; extend with filters when real scrapers land."""

    interval: str = "5m"


@dataclass(frozen=True)
class SearchAgentOutput:
    """Assets to run through data/prediction plus optional market context."""

    assets: tuple[AssetSymbol, ...]
    markets_by_source: dict[str, list[dict[str, Any]]]
    summary: str


class SearchAgent:
    """
    Picks which crypto assets to analyze and attaches a lightweight market snapshot.

    Pulls Polymarket/Kalshi market context with Apify/API providers.
    Falls back to simulated rows when integrations are unavailable.
    """

    def __init__(
        self,
        settings: Settings,
    ) -> None:
        self._settings = settings
        self._apify: ApifyClient | None = None
        if settings.enable_apify and settings.apify_token:
            self._apify = ApifyClient(settings.apify_token, timeout_s=settings.apify_timeout_s)

    def run(self, inp: SearchAgentInput) -> SearchAgentOutput:
        try:
            poly_rows = fetch_polymarket_rows(
                apify=self._apify,
                apify_actor_id=self._settings.apify_polymarket_actor_id,
            )
            kalshi_rows = fetch_kalshi_rows(
                apify=self._apify,
                apify_actor_id=self._settings.apify_kalshi_actor_id,
            )
        except Exception as exc:
            log.exception("SearchAgent: market provider callable failed")
            raise AgentError("SearchAgent", "prediction-market fetch failed") from exc

        if not poly_rows:
            if self._settings.strict_integrations:
                raise AgentError("SearchAgent", "Polymarket source unavailable in strict mode")
            poly_rows = simulate_polymarket_crypto_markets()
        if not kalshi_rows:
            if self._settings.strict_integrations:
                raise AgentError("SearchAgent", "Kalshi source unavailable in strict mode")
            kalshi_rows = simulate_kalshi_crypto_markets()

        markets_by_source = {"polymarket": poly_rows, "kalshi": kalshi_rows}

        assets = self._assets_to_analyze(poly_rows, kalshi_rows)
        summary = _build_context_summary(
            assets=assets,
            interval=inp.interval,
            markets_by_source=markets_by_source,
        )

        log.info(
            "SearchAgent: assets=%s polymarket_rows=%s kalshi_rows=%s",
            assets,
            len(poly_rows),
            len(kalshi_rows),
        )
        return SearchAgentOutput(
            assets=assets,
            markets_by_source=markets_by_source,
            summary=summary,
        )

    def _assets_to_analyze(
        self,
        poly_rows: list[dict[str, Any]],
        kalshi_rows: list[dict[str, Any]],
    ) -> tuple[AssetSymbol, ...]:
        """
        Prefer assets referenced in simulated market rows (``asset`` = BTC|ETH).

        Falls back to ``("BTC", "ETH")`` when none match, so the pipeline always
        has a sensible default until scrapers widen the universe.
        """
        allowed: tuple[AssetSymbol, AssetSymbol] = ("BTC", "ETH")
        ordered: list[AssetSymbol] = []
        for row in (*poly_rows, *kalshi_rows):
            raw = row.get("asset")
            if raw in allowed and raw not in ordered:
                ordered.append(raw)  # type: ignore[arg-type]
        return tuple(ordered) if ordered else allowed


def _build_context_summary(
    *,
    assets: tuple[AssetSymbol, ...],
    interval: str,
    markets_by_source: dict[str, list[dict[str, Any]]],
) -> str:
    lines = [
        f"Assets to analyze: {', '.join(assets)}.",
        f"Spot feature interval (pipeline): {interval}.",
        "Prediction markets (simulated, not scraped):",
    ]
    for source, rows in markets_by_source.items():
        lines.append(f"- {source}: {len(rows)} row(s)")
        for r in rows[:2]:
            title = r.get("question") or r.get("title", "n/a")
            lines.append(f"    · {title}")
        if len(rows) > 2:
            lines.append(f"    · … +{len(rows) - 2} more (simulated)")
    lines.append("Rows come from Apify/API first; simulated data is fallback only.")
    return "\n".join(lines)
