"""Maps prediction confidence to Kelly-based position size in [0, 1]."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from agents.exceptions import AgentError
from agents.prediction_agent import SymbolPrediction
from config import Settings
from services.kelly import kelly_fraction

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskAgentInput:
    """One or more predictions (direction + confidence per symbol)."""

    predictions: tuple[SymbolPrediction, ...]


@dataclass(frozen=True)
class RiskAgentOutput:
    """Suggested position size as a fraction of bankroll per symbol (0–1)."""

    position_size_by_symbol: dict[str, float]


class RiskAgent:
    """
    Treats **confidence** as the win probability ``p`` for the predicted side,
    applies Kelly with **b = 1**, then floors negative Kelly at **0** and clamps to **[0, 1]**.

    Optional scaling from ``Settings`` (fractional Kelly cap and hard max stake)
    keeps sizes conservative in live trading.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(self, inp: RiskAgentInput) -> RiskAgentOutput:
        out: dict[str, float] = {}
        for pred in inp.predictions:
            p = self._probability(pred.confidence)
            try:
                raw = kelly_fraction(p=p, b=1.0)
            except ValueError as exc:
                log.exception("RiskAgent: Kelly input invalid for %s", pred.symbol)
                raise AgentError("RiskAgent", f"invalid probability for {pred.symbol}") from exc
            # Negative Kelly → no edge; stay flat (position 0).
            safe = max(0.0, min(1.0, raw))

            scaled = safe * self._settings.kelly_fraction
            capped = min(scaled, self._settings.max_kelly_stake)
            final_size = float(min(1.0, max(0.0, capped)))

            out[pred.symbol] = final_size
            log.info(
                "Risk %s dir=%s p=%.4f raw_kelly=%.4f safe_kelly=%.4f position=%.4f",
                pred.symbol,
                pred.direction,
                p,
                raw,
                safe,
                final_size,
            )

        return RiskAgentOutput(position_size_by_symbol=out)

    @staticmethod
    def _probability(confidence: float) -> float:
        """Clamp model confidence into a valid probability for Kelly."""
        return min(1.0, max(0.0, float(confidence)))
