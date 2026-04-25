"""Minimal Apify API client for actor runs and dataset fetches."""

from __future__ import annotations

from typing import Any

import httpx


class ApifyClient:
    def __init__(self, token: str, *, timeout_s: float = 45.0) -> None:
        self._token = token
        self._timeout_s = timeout_s
        self._base_url = "https://api.apify.com/v2"

    def run_actor_and_get_items(
        self,
        *,
        actor_id: str,
        actor_input: dict[str, Any] | None = None,
        max_items: int = 50,
    ) -> list[dict[str, Any]]:
        actor_input = actor_input or {}
        run = self._start_actor(actor_id=actor_id, actor_input=actor_input)
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return []
        return self._get_dataset_items(dataset_id=dataset_id, max_items=max_items)

    def _start_actor(self, *, actor_id: str, actor_input: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/acts/{actor_id}/runs"
        params = {"token": self._token, "waitForFinish": 120}
        with httpx.Client(timeout=self._timeout_s) as client:
            res = client.post(url, params=params, json=actor_input)
            res.raise_for_status()
            payload = res.json()
        return payload.get("data", {})

    def _get_dataset_items(self, *, dataset_id: str, max_items: int) -> list[dict[str, Any]]:
        url = f"{self._base_url}/datasets/{dataset_id}/items"
        params = {
            "token": self._token,
            "clean": "true",
            "desc": "true",
            "limit": max_items,
        }
        with httpx.Client(timeout=self._timeout_s) as client:
            res = client.get(url, params=params)
            res.raise_for_status()
            payload = res.json()
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        return []
