"""Shared errors for agent boundaries."""

from __future__ import annotations


class AgentError(RuntimeError):
    """Raised when a named agent step fails; original exception is chained with ``raise ... from``."""

    def __init__(self, agent_name: str, message: str) -> None:
        self.agent_name = agent_name
        super().__init__(f"[{agent_name}] {message}")
