"""Google Cloud Vertex AI (Model Garden / Gemini) LLM provider (PRD §7.1).

Requires ``JAIL_LLM_PROVIDER=vertex`` plus GCP credentials. Raises an explicit
LLMUnavailableError when unavailable — never falls back to another provider.
"""

from __future__ import annotations

from app.core.errors import LLMUnavailableError
from app.llm.base import LLMProvider


class VertexAIProvider(LLMProvider):
    name = "vertex"

    def __init__(
        self,
        project: str | None = None,
        location: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        from app.config import get_settings

        s = get_settings()
        self.project = project or s.vertex_project
        self.location = location or s.vertex_location
        self.model = model or s.vertex_model
        self.temperature = temperature if temperature is not None else s.llm_temperature
        self.max_tokens = max_tokens or s.llm_max_tokens

    def _client(self):
        try:
            import importlib

            genai = importlib.import_module("google.genai")
        except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover
            raise LLMUnavailableError(
                "Vertex AI provider selected but `google-genai` is not installed. "
                "Install backend/requirements-cloud.txt and configure GCP credentials."
            ) from exc
        return genai.Client(vertexai=True, project=self.project, location=self.location)

    def chat(
        self, system: str, messages: list[dict], *, max_tokens: int | None = None
    ) -> str:
        client = self._client()
        contents = [self._to_content(m) for m in messages]
        config: dict = {"system_instruction": system}
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        if tokens is not None:
            config["max_output_tokens"] = tokens
        if self.temperature is not None:
            config["temperature"] = self.temperature
        try:
            resp = client.models.generate_content(
                model=self.model, contents=contents, config=config
            )
            return (resp.text or "").strip()
        except Exception as exc:
            raise LLMUnavailableError(
                f"Configured Vertex AI endpoint unavailable: {exc}. No fallback model is used."
            ) from exc


    @staticmethod
    def _to_content(message: dict) -> dict:
        return {
            "role": message.get("role"),
            "parts": [{"text": message.get("content", "")}],
        }
