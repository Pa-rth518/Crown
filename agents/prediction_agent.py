"""Rule-based next-bar direction from recent OHLCV; optional Kronos hook."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from agents.exceptions import AgentError
from config import Settings
from services.kronos_adapter import KronosAdapter
from services.openrouter_client import OpenRouterClient

log = logging.getLogger(__name__)

Direction = Literal["UP", "DOWN"]

# Binance klines max per request; we only need the trailing window for features.
MAX_INPUT_CANDLES = 1000
TREND_WINDOW = 5


@dataclass(frozen=True)
class SymbolPrediction:
    """One symbol forecast."""

    symbol: str
    direction: Direction
    confidence: float
    rationale: str


@dataclass(frozen=True)
class PredictionAgentInput:
    """Candles plus optional LLM context."""

    candles_by_symbol: dict[str, list[dict[str, Any]]]
    context_summary: str


@dataclass(frozen=True)
class PredictionAgentOutput:
    """Batch predictions for the cycle."""

    cycle_id: str
    predictions: tuple[SymbolPrediction, ...]


class PredictionAgent:
    """
    Predicts whether the **next** move is UP or DOWN using the last candles.

    Default rule: if the **last 5** closes show an upward trend (last close
    above the first close of that window) → UP; otherwise → DOWN. Confidence
    is a bounded score in ``[0, 1]`` from the strength of that 5-bar move.

    Set ``use_kronos=True`` after integrating a Kronos model; until then the
    placeholder returns ``None`` and rules always apply.
    """

    def __init__(self, settings: Settings, *, use_kronos: bool = False) -> None:
        self._settings = settings
        self._use_kronos = use_kronos or settings.enable_kronos
        self._kronos = KronosAdapter(enabled=self._use_kronos, repo_path=settings.kronos_repo_path)
        self._llm: OpenRouterClient | None = None
        if settings.enable_llm_reasoning and settings.openrouter_api_key:
            self._llm = OpenRouterClient(
                api_key=settings.openrouter_api_key,
                model=settings.llm_model,
                base_url=settings.openrouter_base_url,
                app_name=settings.app_name,
                fallback_models=settings.llm_fallback_models,
            )

    def run(self, inp: PredictionAgentInput) -> PredictionAgentOutput:
        cycle_id = str(uuid.uuid4())
        preds: list[SymbolPrediction] = []

        try:
            for symbol, rows in inp.candles_by_symbol.items():
                candles = self._last_n_candles(rows, MAX_INPUT_CANDLES)
                kronos = self._kronos_forecast_optional(symbol, candles)
                if kronos is not None:
                    direction, confidence, rationale = kronos
                else:
                    closes = self._closes(candles)
                    direction, confidence, rationale = self._rule_based_signal(closes)
                rationale = self._refine_rationale_with_llm(
                    symbol=symbol,
                    direction=direction,
                    confidence=confidence,
                    base_rationale=rationale,
                    context_summary=inp.context_summary,
                )

                preds.append(
                    SymbolPrediction(
                        symbol=symbol,
                        direction=direction,
                        confidence=confidence,
                        rationale=rationale,
                    )
                )
                log.info("%s prediction=%s conf=%.3f", symbol, direction, confidence)
        except ValueError as exc:
            log.exception("PredictionAgent: invalid candle window")
            raise AgentError("PredictionAgent", str(exc)) from exc

        _ = inp.context_summary  # reserved for regime / fusion with Kronos later
        return PredictionAgentOutput(cycle_id=cycle_id, predictions=tuple(preds))

    @staticmethod
    def _last_n_candles(rows: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
        """Keep at most the last ``n`` candles (newest at end)."""
        if len(rows) <= n:
            return list(rows)
        return list(rows[-n:])

    @staticmethod
    def _closes(candles: list[dict[str, Any]]) -> list[float]:
        out: list[float] = []
        for c in candles:
            if isinstance(c, dict) and "close" in c:
                out.append(float(c["close"]))
        return out

    def _rule_based_signal(self, closes: list[float]) -> tuple[Direction, float, str]:
        """
        UP iff the last ``TREND_WINDOW`` closes trend up (end > start of window).

        Confidence scales with the magnitude of the relative move over that window.
        """
        if len(closes) < TREND_WINDOW:
            raise ValueError(f"Need at least {TREND_WINDOW} closes; got {len(closes)}.")

        start = closes[-TREND_WINDOW]
        end = closes[-1]

        if start <= 0:
            rationale = "Invalid window start price; defaulting to DOWN."
            log.warning(rationale)
            return "DOWN", 0.55, rationale

        upward = end > start
        direction: Direction = "UP" if upward else "DOWN"

        rel_move = (end - start) / start
        strength = abs(rel_move)
        # Map strength to [0.5, 1.0]: flat move → ~0.5, larger move → higher
        confidence = float(min(1.0, max(0.0, 0.5 + min(strength * 40.0, 0.5))))

        rationale = (
            f"Last {MAX_INPUT_CANDLES} candles considered; "
            f"{TREND_WINDOW}-bar window: {start:.8g} → {end:.8g} "
            f"({'uptrend' if upward else 'not uptrend'} on {self._settings.kline_interval})."
        )
        return direction, confidence, rationale

    def _kronos_forecast_optional(
        self,
        symbol: str,
        candles: list[dict[str, Any]],
    ) -> tuple[Direction, float, str] | None:
        """
        Optional Kronos model path.

        Returns ``None`` to keep using rule-based logic. When Kronos is wired,
        return ``(direction, confidence, rationale)`` here.
        """
        if not self._use_kronos:
            return None
        out = self._kronos.predict(symbol=symbol, candles=candles)
        if out is None:
            log.debug("Kronos unavailable for %s; fallback to rule model.", symbol)
        return out

    def _refine_rationale_with_llm(
        self,
        *,
        symbol: str,
        direction: Direction,
        confidence: float,
        base_rationale: str,
        context_summary: str,
    ) -> str:
        if self._llm is None:
            return base_rationale
        prompt = (
            "You are a quant assistant. Rewrite this prediction rationale in 1-2 short "
            "sentences, no hype, no financial advice. "
            f"Symbol={symbol}, direction={direction}, confidence={confidence:.4f}. "
            f"Base rationale: {base_rationale}\n"
            f"Market context:\n{context_summary}"
        )
        try:
            llm_text = self._llm.complete(prompt).strip()
        except Exception as exc:
            log.debug("OpenRouter rationale generation failed: %s", exc)
            return base_rationale
        return llm_text or base_rationale
