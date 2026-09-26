"""Domain exceptions and global error mapping (explicit, never silent)."""

from __future__ import annotations


class JurisFlowError(Exception):
    """Base error. Defined status_code for JSON mapping."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class LLMUnavailableError(JurisFlowError):
    """A configured LLM endpoint is unavailable. Operations must fail explicitly (PRD §10.2)."""

    status_code = 503
    code = "llm_unavailable"


class EmbeddingError(JurisFlowError):
    status_code = 503
    code = "embedding_unavailable"


class VectorStoreError(JurisFlowError):
    status_code = 503
    code = "vector_store_unavailable"


class NotFoundError(JurisFlowError):
    status_code = 404
    code = "not_found"


class PermissionDeniedError(JurisFlowError):
    status_code = 403
    code = "permission_denied"


class UnauthorizedError(JurisFlowError):
    status_code = 401
    code = "unauthorized"


class ValidationError(JurisFlowError):
    status_code = 422
    code = "validation_error"


class PolicyDeniedError(JurisFlowError):
    status_code = 403
    code = "policy_denied"


class AbuseError(JurisFlowError):
    status_code = 429
    code = "rate_limited"


class ConflictError(JurisFlowError):
    status_code = 409
    code = "conflict"
