"""OpenRouter chat completion helper."""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        app_name: str,
        fallback_models: tuple[str, ...] = (),
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._app_name = app_name
        ordered = [model, *fallback_models]
        deduped: list[str] = []
        for m in ordered:
            mm = m.strip()
            if mm and mm not in deduped:
                deduped.append(mm)
        self._models = tuple(deduped)

    def complete(self, prompt: str) -> str:
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost/crowd-wisdom",
            "X-Title": self._app_name,
        }
        with httpx.Client(timeout=30.0) as client:
            for model_id in self._models:
                payload: dict[str, Any] = {
                    "model": model_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                }
                try:
                    res = client.post(url, headers=headers, json=payload)
                    res.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    body = ""
                    if exc.response is not None:
                        body = exc.response.text[:300]
                    log.warning(
                        "OpenRouter request failed for model=%s status=%s body=%s",
                        model_id,
                        exc.response.status_code if exc.response is not None else "n/a",
                        body,
                    )
                    continue
                except httpx.HTTPError as exc:
                    log.warning("OpenRouter request error for model=%s: %s", model_id, exc)
                    continue

                body = res.json()
                choices = body.get("choices", []) if isinstance(body, dict) else []
                if not choices:
                    continue
                msg = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    return content
        return ""
