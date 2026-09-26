"""LLM provider interface (PRD §7.1).

No fallback or silent substitution: if the configured provider is unavailable
the operation must raise ``LLMUnavailableError`` (PRD §10.2, §15.1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def chat(
        self, system: str, messages: list[dict], *, max_tokens: int | None = None
    ) -> str:
        """Send a chat request. messages: [{"role": user|assistant, "content": str}]."""

    def complete(self, prompt: str) -> str:
        return self.chat(
            "You are a precise, safe assistant.", [{"role": "user", "content": prompt}]
        )
