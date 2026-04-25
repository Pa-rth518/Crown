"""Hermes-style orchestration helpers.

This module keeps a thin boundary where real Hermes runtime objects can be added
without changing agent contracts in the rest of the project.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from agents.exceptions import AgentError

T = TypeVar("T")


class HermesLoop:
    """Sequential orchestrator with Hermes-compatible step boundary behavior."""

    def run_step(self, agent_name: str, fn: Callable[[], T]) -> T:
        try:
            return fn()
        except AgentError:
            raise
        except Exception as exc:  # pragma: no cover - wrapper behavior
            raise AgentError(agent_name, f"{type(exc).__name__}: {exc}") from exc
