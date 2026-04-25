"""Search → Data → Prediction → Risk → Feedback orchestration."""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from agents.data_agent import DataAgent, DataAgentInput
from agents.feedback_agent import FeedbackAgent, FeedbackAgentInput
from agents.prediction_agent import PredictionAgent, PredictionAgentInput
from agents.risk_agent import RiskAgent, RiskAgentInput
from agents.search_agent import SearchAgent, SearchAgentInput
from config import Settings
from services.hermes_loop import HermesLoop

log = logging.getLogger(__name__)

T = TypeVar("T")


def _short_symbol(binance_symbol: str) -> str:
    u = binance_symbol.strip().upper()
    if u.endswith("USDT") and len(u) > 4:
        return u[: -len("USDT")]
    return u


def run_pipeline(settings: Settings, *, print_summary: bool = True) -> int:
    """
    Execute the full agent chain.

    Returns ``0`` on success. Failures surface as :class:`~agents.exceptions.AgentError` or other exceptions to the caller.
    """
    log.info("=== Pipeline start (interval=%s) ===", settings.kline_interval)
    loop = HermesLoop()

    log.info("Step 1/5 Search: resolving assets and simulated prediction markets")
    search = SearchAgent(settings=settings)
    search_out = loop.run_step(
        "SearchAgent",
        lambda: search.run(SearchAgentInput(interval=settings.kline_interval)),
    )
    log.info(
        "Step 1/5 Search done: assets=%s polymarket=%s kalshi=%s row(s)",
        search_out.assets,
        len(search_out.markets_by_source.get("polymarket", ())),
        len(search_out.markets_by_source.get("kalshi", ())),
    )

    log.info("Step 2/5 Data: fetching OHLCV for %s", search_out.assets)
    data = DataAgent(settings=settings)
    candles_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for asset in search_out.assets:
        d_out = loop.run_step(
            "DataAgent",
            lambda a=asset: data.run(DataAgentInput(asset=a)),
        )
        candles_by_symbol[d_out.binance_symbol] = list(d_out.candles)
        log.info(
            "Step 2/5 Data: %s → %s candles (interval=%s)",
            asset,
            len(d_out.candles),
            d_out.interval,
        )
    log.info("Step 2/5 Data done: %s pair(s) loaded", len(candles_by_symbol))

    log.info("Step 3/5 Prediction: running models on loaded candles")
    predict = PredictionAgent(settings=settings)
    pred_out = loop.run_step(
        "PredictionAgent",
        lambda: predict.run(
            PredictionAgentInput(
                candles_by_symbol=candles_by_symbol,
                context_summary=search_out.summary,
            )
        ),
    )
    for p in pred_out.predictions:
        log.info(
            "Step 3/5 Prediction: %s → %s (confidence=%.4f)",
            p.symbol,
            p.direction,
            p.confidence,
        )
    log.info("Step 3/5 Prediction done (cycle_id=%s)", pred_out.cycle_id)

    log.info("Step 4/5 Risk: Kelly position sizing from confidence")
    risk = RiskAgent(settings=settings)
    risk_out = loop.run_step(
        "RiskAgent",
        lambda: risk.run(RiskAgentInput(predictions=pred_out.predictions)),
    )
    for sym, size in risk_out.position_size_by_symbol.items():
        log.info("Step 4/5 Risk: %s → position_size=%.4f", sym, size)
    log.info("Step 4/5 Risk done")

    if print_summary:
        print("")
        print("--- Results ---")
        for p in pred_out.predictions:
            pos = risk_out.position_size_by_symbol.get(p.symbol, 0.0)
            label = _short_symbol(p.symbol)
            line = f"{label} → {p.direction} → confidence: {p.confidence:.2f} → position size: {pos:.2f}"
            print(line)
            log.info("Summary line: %s", line)
        print("")

    log.info("Step 5/5 Feedback: persisting predictions and settling prior rows")
    feedback = FeedbackAgent(settings=settings)
    last_close_by_symbol: dict[str, float] = {}
    for sym, candles in candles_by_symbol.items():
        if candles and isinstance(candles[-1], dict) and "close" in candles[-1]:
            last_close_by_symbol[sym] = float(candles[-1]["close"])

    fb_out = loop.run_step(
        "FeedbackAgent",
        lambda: feedback.run(
            FeedbackAgentInput(
                cycle_id=pred_out.cycle_id,
                predictions=pred_out.predictions,
                last_close_by_symbol=last_close_by_symbol,
                notes="Settled when a later run shows a moved close vs reference_close.",
            )
        ),
    )
    log.info(
        "Step 5/5 Feedback done: ledger=%s settled_total=%s accuracy=%s",
        fb_out.ledger_path,
        fb_out.summary.get("settled_total"),
        fb_out.summary.get("accuracy"),
    )

    log.info("=== Pipeline complete ===")
    return 0
