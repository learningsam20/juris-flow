"""Application configuration, driven by environment / .env file.

Env vars follow the JAIL_ prefix (JurisFlow). A complete set of documented
variables lives in `.env.example`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        env_prefix="JAIL_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App -----------------------------------------------------------------
    app_name: str = "JurisFlow"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5601"

    # --- Security -----------------------------------------------------------
    secret_key: str = "dev-only-change-me"
    access_token_minutes: int = 120
    refresh_token_minutes: int = 60 * 24 * 7
    algorithm: str = "HS256"
    auth_provider: str = "form"  # "form" | "keycloak"
    keycloak_url: str = ""
    keycloak_realm: str = ""
    keycloak_client_id: str = ""
    keycloak_client_secret: str = ""
    rate_limit_enabled: bool = True

    # --- Database -----------------------------------------------------------
    database_url: str = "sqlite:///./data/jurisflow.db"

    # --- Storage ------------------------------------------------------------
    storage_backend: str = "local"  # "local" | "gcs"
    data_dir: str = "data"
    upload_dir: str = "data/uploads"
    document_bucket: str = ""

    # --- LLM (no fallback: provider must succeed or operations fail) --------
    llm_provider: str = "ollama"  # "ollama" | "vertex"
    ollama_base_url: str = "http://localhost:11434"
    llm_model: str = "llama3.2:latest"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096
    # Dedicated, stronger model for Ask AI (grounded Q&A). Defaults differ from
    # the general review/simulation model and skew toward low-temperature facts.
    ask_llm_model: str = "gemma4:latest"
    ask_llm_temperature: float = 0.1
    ask_llm_max_tokens: int = 8192
    vertex_project: str = ""
    vertex_location: str = "us-central1"
    vertex_model: str = "gemini-2.5-flash"
    vertex_service_account: str = ""

    # --- Embeddings ---------------------------------------------------------
    embedding_provider: str = "ollama"
    embedding_model: str = "all-minilm"
    embedding_dimensions: int = 384
    embedding_batch_size: int = 32  # Ollama /api/embed rejects oversized single batches
    vertex_embedding_model: str = "text-embedding-005"

    # --- Vector store -------------------------------------------------------
    vector_provider: str = "qdrant"  # "qdrant" | "vertex"
    qdrant_url: str = ""  # empty -> embedded local mode
    qdrant_path: str = "data/qdrant"
    qdrant_api_key: str = ""
    vertex_vector_index: str = ""
    vertex_vector_endpoint: str = ""
    vertex_vector_distance: str = "COSINE"

    # --- Ingestion ----------------------------------------------------------
    max_upload_mb: int = 20
    chunk_size: int = 800
    chunk_overlap: int = 120
    allowed_doc_types: str = "pdf,docx,txt,md"
    ocr_enabled: bool = True
    ocr_provider: str = "tesseract"  # "tesseract" | "ollama_vision"
    ocr_vision_model: str = "openbmb/minicpm-v4.6:latest"
    ocr_vision_base_url: str = "http://localhost:11434"
    ocr_max_pages: int = 50

    # --- Sim -----------------------------------------------------------------
    default_turn_limit: int = 8
    sim_poll_interval: float = 1.0
    # Cap local-LLM generation so tribunal turns finish quickly (4096 hung Ollama).
    sim_llm_max_tokens: int = 512
    sim_llm_timeout_seconds: float = 45.0
    sim_llm_num_ctx: int = 4096
    # LLM-as-judge winner ruling: deliberation "effort" and the number of litigant
    # exchanges ("conversations") allowed before the judge must decide which side
    # (plaintiff = legal counsel, defendant = opponent) won the case.
    sim_judge_effort: str = "medium"  # "low" | "medium" | "high"
    sim_judge_max_rounds: int = 3

    # --- Sim audio / TTS ----------------------------------------------------
    tts_enabled: bool = True
    # "edge" = Microsoft Edge neural TTS (online, distinct voices per role, mp3).
    # "macos" = local macOS `say` (offline; dev-only; m4a/aiff unless ffmpeg).
    # "none"  = disable synthesis (records no-audio status).
    tts_provider: str = "edge"
    tts_data_dir: str = "data/media/simulations"
    # Optional per-role voice overrides as json, e.g.
    # {"judge": "en-US-GuyNeural", "plaintiff": "en-US-AriaNeural"}
    tts_voices: str = ""

    # --- Observability ------------------------------------------------------
    log_level: str = "INFO"
    otel_exporter_otlp_endpoint: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_documents(self) -> list[str]:
        return [
            t.strip().lower() for t in self.allowed_doc_types.split(",") if t.strip()
        ]

    @model_validator(mode="after")
    def _anchor_paths(self) -> Settings:
        """Resolve relative SQLite and data directory paths against the backend directory.

        A relative path like ``sqlite:///./data/jurisflow.db`` or ``data/uploads`` otherwise
        depends on the process CWD, so starting uvicorn from the repo root vs. ``backend/``
        previously created duplicate ``data/`` folders at both locations.
        """
        url = self.database_url
        if url.startswith("sqlite:///"):
            path = url[len("sqlite:///") :]
            if path and path != ":memory:" and not Path(path).is_absolute():
                self.database_url = f"sqlite:///{(BACKEND_DIR / path).resolve()}"

        if self.data_dir and not Path(self.data_dir).is_absolute():
            self.data_dir = str((BACKEND_DIR / self.data_dir).resolve())

        if self.upload_dir and not Path(self.upload_dir).is_absolute():
            self.upload_dir = str((BACKEND_DIR / self.upload_dir).resolve())

        if self.qdrant_path and not Path(self.qdrant_path).is_absolute():
            self.qdrant_path = str((BACKEND_DIR / self.qdrant_path).resolve())

        if self.tts_data_dir and not Path(self.tts_data_dir).is_absolute():
            self.tts_data_dir = str((BACKEND_DIR / self.tts_data_dir).resolve())

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
