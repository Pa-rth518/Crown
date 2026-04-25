"""Kronos integration shim with safe fallback behavior."""

from __future__ import annotations

import importlib
import logging
import os
import sys
from typing import Any, Literal

Direction = Literal["UP", "DOWN"]
log = logging.getLogger(__name__)


class KronosAdapter:
    """Light adapter around Kronos-style inference call."""

    def __init__(self, enabled: bool = True, repo_path: str | None = None) -> None:
        self._enabled = enabled
        self._repo_path = repo_path
        self._predictor: Any = None
        self._load_predictor()

    def predict(self, *, symbol: str, candles: list[dict[str, Any]]) -> tuple[Direction, float, str] | None:
        if not self._enabled:
            return None
        if len(candles) < 2:
            return None

        if callable(self._predictor):
            try:
                raw = self._predictor(symbol=symbol, candles=candles)
                parsed = self._normalize_prediction(raw)
                if parsed is not None:
                    return parsed
            except Exception as exc:
                log.warning("Kronos predictor call failed, using fallback: %s", exc)

        return self._fallback_prediction(symbol=symbol, candles=candles)

    def _load_predictor(self) -> None:
        candidates = ("kronos", "inference", "kronos_inference")
        if self._repo_path:
            repo = self._repo_path.strip()
            if repo and os.path.isdir(repo) and repo not in sys.path:
                sys.path.insert(0, repo)
        for mod_name in candidates:
            try:
                mod = importlib.import_module(mod_name)
            except Exception:
                continue
            for attr in ("predict_next_move", "predict", "infer"):
                fn = getattr(mod, attr, None)
                if callable(fn):
                    self._predictor = fn
                    log.info("Kronos callable loaded: %s.%s", mod_name, attr)
                    return

    @staticmethod
    def _normalize_prediction(raw: Any) -> tuple[Direction, float, str] | None:
        if isinstance(raw, dict):
            direction = str(raw.get("direction", "")).upper()
            confidence = float(raw.get("confidence", 0.55))
            rationale = str(raw.get("rationale", "Kronos model output"))
            if direction in ("UP", "DOWN"):
                return direction, max(0.0, min(1.0, confidence)), rationale
        if isinstance(raw, tuple) and len(raw) >= 2:
            direction = str(raw[0]).upper()
            confidence = float(raw[1])
            rationale = str(raw[2]) if len(raw) >= 3 else "Kronos tuple output"
            if direction in ("UP", "DOWN"):
                return direction, max(0.0, min(1.0, confidence)), rationale
        if isinstance(raw, str):
            direction = raw.strip().upper()
            if direction in ("UP", "DOWN"):
                return direction, 0.6, "Kronos string output"
        return None

    @staticmethod
    def _fallback_prediction(*, symbol: str, candles: list[dict[str, Any]]) -> tuple[Direction, float, str] | None:
        closes = [float(c["close"]) for c in candles if isinstance(c, dict) and "close" in c]
        if len(closes) < 10:
            return None
        recent = closes[-5:]
        older = closes[-10:-5]
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        if older_avg <= 0:
            return None
        rel = (recent_avg - older_avg) / older_avg
        direction: Direction = "UP" if rel > 0 else "DOWN"
        confidence = max(0.5, min(0.9, 0.5 + min(abs(rel) * 20.0, 0.4)))
        rationale = (
            f"Kronos fallback signal for {symbol}: 5-bar mean vs previous 5-bar mean "
            f"({older_avg:.6g} -> {recent_avg:.6g})."
        )
        return direction, confidence, rationale
