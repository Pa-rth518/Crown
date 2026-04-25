"""Persist predictions, settle vs realized price move, track rolling accuracy."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from agents.exceptions import AgentError
from agents.prediction_agent import SymbolPrediction
from config import Settings

log = logging.getLogger(__name__)

Direction = Literal["UP", "DOWN"]


@dataclass(frozen=True)
class FeedbackAgentInput:
    """Predictions plus latest close per symbol to settle prior forecasts."""

    cycle_id: str
    predictions: tuple[SymbolPrediction, ...]
    """Latest completed candle close for each symbol (same series used to predict)."""

    last_close_by_symbol: dict[str, float]
    notes: str = ""


@dataclass(frozen=True)
class FeedbackAgentOutput:
    """Result of the feedback pass."""

    ledger_path: str
    summary: dict[str, Any]
    new_records: tuple[dict[str, Any], ...]


class FeedbackAgent:
    """
    Writes a single local JSON file (see ``Settings.feedback_store_path``).

    Each run: (1) settle any pending rows when price has moved from ``reference_close``,
    (2) append new pending rows for this cycle, (3) recompute ``summary`` accuracy
    over all settled rows.
    """

    def __init__(self, settings: Settings) -> None:
        self._path = Path(settings.feedback_store_path)

    def run(self, inp: FeedbackAgentInput) -> FeedbackAgentOutput:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.exception("FeedbackAgent: cannot create ledger directory")
            raise AgentError("FeedbackAgent", f"cannot create directory for {self._path}") from exc

        state = self._load()

        settled_now = self._settle_pending(state["predictions"], inp.last_close_by_symbol)
        if settled_now:
            log.info("FeedbackAgent settled %s pending prediction(s)", settled_now)

        created_at = datetime.now(timezone.utc).isoformat()
        new_rows: list[dict[str, Any]] = []
        for p in inp.predictions:
            ref = inp.last_close_by_symbol.get(p.symbol)
            if ref is None:
                log.warning("No reference close for %s; skipping ledger row", p.symbol)
                continue
            row = {
                "cycle_id": inp.cycle_id,
                "symbol": p.symbol,
                "predicted": p.direction,
                "confidence": p.confidence,
                "rationale": p.rationale,
                "reference_close": ref,
                "created_at": created_at,
                "notes": inp.notes,
                "settled": False,
                "actual": None,
                "correct": None,
                "settled_at": None,
            }
            state["predictions"].append(row)
            new_rows.append(row)

        state["summary"] = self._build_summary(state["predictions"])
        self._save(state)

        log.info(
            "FeedbackAgent wrote %s (accuracy=%s over %s settled)",
            self._path,
            state["summary"].get("accuracy"),
            state["summary"].get("settled_total"),
        )
        return FeedbackAgentOutput(
            ledger_path=str(self._path),
            summary=state["summary"],
            new_records=tuple(new_rows),
        )

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"predictions": [], "summary": self._empty_summary()}
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            log.error("Feedback ledger unreadable (%s); starting fresh.", exc)
            return {"predictions": [], "summary": self._empty_summary()}

        if not isinstance(data, dict):
            return {"predictions": [], "summary": self._empty_summary()}
        preds = data.get("predictions")
        if not isinstance(preds, list):
            preds = []
        return {"predictions": preds, "summary": data.get("summary") or self._empty_summary()}

    def _save(self, state: dict[str, Any]) -> None:
        try:
            self._path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except OSError as exc:
            log.exception("FeedbackAgent: cannot write ledger")
            raise AgentError("FeedbackAgent", f"cannot write ledger {self._path}") from exc

    @staticmethod
    def _empty_summary() -> dict[str, Any]:
        return {"settled_total": 0, "settled_correct": 0, "accuracy": None}

    def _settle_pending(
        self,
        rows: list[dict[str, Any]],
        last_close_by_symbol: dict[str, float],
    ) -> int:
        """Mark pending rows settled when current close differs from stored reference."""
        count = 0
        for row in rows:
            if row.get("settled"):
                continue
            sym = row.get("symbol")
            if not sym or not isinstance(row.get("reference_close"), (int, float)):
                continue
            cur = last_close_by_symbol.get(sym)
            if cur is None:
                continue
            ref = float(row["reference_close"])
            if not self._price_moved(ref, float(cur)):
                continue

            actual: Direction = "UP" if float(cur) > ref else "DOWN"
            predicted = row.get("predicted")
            correct = predicted == actual

            row["settled"] = True
            row["actual"] = actual
            row["correct"] = correct
            row["settled_at"] = datetime.now(timezone.utc).isoformat()
            row["outcome_close"] = float(cur)
            count += 1
            log.debug(
                "Settled %s predicted=%s actual=%s correct=%s ref=%s cur=%s",
                sym,
                predicted,
                actual,
                correct,
                ref,
                cur,
            )
        return count

    @staticmethod
    def _price_moved(ref: float, cur: float, rel_eps: float = 1e-9) -> bool:
        if ref == 0:
            return cur != 0
        return abs(cur - ref) / abs(ref) > rel_eps

    @staticmethod
    def _build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        settled = [r for r in rows if r.get("settled") and r.get("correct") is not None]
        total = len(settled)
        correct = sum(1 for r in settled if r.get("correct") is True)
        accuracy = (correct / total) if total else None
        by_symbol: dict[str, dict[str, Any]] = {}
        for row in settled:
            sym = str(row.get("symbol", "UNKNOWN"))
            if sym not in by_symbol:
                by_symbol[sym] = {"settled_total": 0, "settled_correct": 0, "accuracy": None}
            by_symbol[sym]["settled_total"] += 1
            if row.get("correct") is True:
                by_symbol[sym]["settled_correct"] += 1
        for sym, stats in by_symbol.items():
            s_total = stats["settled_total"]
            s_correct = stats["settled_correct"]
            stats["accuracy"] = round(s_correct / s_total, 4) if s_total else None

        return {
            "settled_total": total,
            "settled_correct": correct,
            "accuracy": round(accuracy, 4) if accuracy is not None else None,
            "by_symbol": by_symbol,
        }
