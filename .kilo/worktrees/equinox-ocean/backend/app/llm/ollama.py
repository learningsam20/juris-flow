"""Ollama LLM provider (local/open-source, dev default)."""

from __future__ import annotations

import requests

from app.config import get_settings
from app.core.errors import LLMUnavailableError
from app.core.logging import get_correlation_id
from app.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        s = get_settings()
        self.base_url = (base_url or s.ollama_base_url).rstrip("/")
        self.model = model or s.llm_model
        self.temperature = s.llm_temperature if temperature is None else temperature
        self.max_tokens = s.llm_max_tokens if max_tokens is None else max_tokens

    def chat(
        self, system: str, messages: list[dict], *, max_tokens: int | None = None
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": max_tokens or self.max_tokens,
                "num_ctx": 8192,
            },
            "keep_alive": "15m",
        }
        try:
            resp = self._requests_post(payload)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise LLMUnavailableError(f"Ollama error: {data['error']}")
            return str(data.get("message", {}).get("content", "")).strip()
        except LLMUnavailableError:
            raise
        except requests.RequestException as exc:
            raise LLMUnavailableError(
                f"Configured LLM endpoint `{self.base_url}` unavailable: {exc}. "
                "No fallback model is used; retry when the endpoint is reachable."
            ) from exc

    def _requests_post(self, payload: dict):
        import logging

        logger = logging.getLogger("llm.ollama")
        logger.info(
            "ollama.chat",
            extra={"model": self.model, "correlation_id": get_correlation_id()},
        )
        return requests.post(f"{self.base_url}/api/chat", json=payload, timeout=60)
