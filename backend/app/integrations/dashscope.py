from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings


class ProviderConfigurationError(RuntimeError):
    pass


class ProviderTimeoutError(RuntimeError):
    pass


class ProviderAuthenticationError(RuntimeError):
    pass


class ProviderResponseError(RuntimeError):
    pass


@dataclass(frozen=True)
class StandardizedProviderError:
    code: str
    message: str


@dataclass(frozen=True)
class ChatGeneration:
    answer_text: str
    usage: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    model: str


class FakeDashScopeClient:
    def __init__(
        self,
        *,
        chat_answer: str = "This answer is based on approved sources.",
        embedding: list[float] | None = None,
        embedding_model: str = "fake-embedding",
        embedding_error: Exception | None = None,
        chat_error: Exception | None = None,
    ) -> None:
        self.chat_answer = chat_answer
        self.embedding = embedding or [0.01, 0.02, 0.03]
        self.embedding_model = embedding_model
        self.embedding_error = embedding_error
        self.chat_error = chat_error
        self.embedding_requests: list[str] = []
        self.chat_requests: list[dict[str, Any]] = []

    def embed_text(self, text: str) -> EmbeddingResult:
        self.embedding_requests.append(text)
        if self.embedding_error is not None:
            raise self.embedding_error
        return EmbeddingResult(vector=list(self.embedding), model=self.embedding_model)

    def generate_answer(self, *, question: str, contexts: list[dict[str, Any]]) -> ChatGeneration:
        self.chat_requests.append({"question": question, "contexts": contexts})
        if self.chat_error is not None:
            raise self.chat_error
        token_estimate = max(1, sum(len(context.get("text", "")) for context in contexts) // 4)
        return ChatGeneration(
            answer_text=self.chat_answer,
            usage={"prompt_tokens": token_estimate, "completion_tokens": max(1, len(self.chat_answer) // 4)},
        )


class DashScopeHttpClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def embed_text(self, text: str) -> EmbeddingResult:
        raise ProviderConfigurationError("Real DashScope embedding calls are not implemented in automated MVP tests.")

    def generate_answer(self, *, question: str, contexts: list[dict[str, Any]]) -> ChatGeneration:
        raise ProviderConfigurationError("Real DashScope chat calls are not implemented in automated MVP tests.")


def create_dashscope_client(settings: Settings | None = None) -> FakeDashScopeClient | DashScopeHttpClient:
    resolved_settings = settings or Settings()
    if resolved_settings.use_fake_external_clients:
        return FakeDashScopeClient(embedding_model=resolved_settings.dashscope_embedding_model)
    if not resolved_settings.dashscope_api_key:
        raise ProviderConfigurationError("DASHSCOPE_API_KEY is required when real external clients are enabled.")
    return DashScopeHttpClient(resolved_settings)


def normalize_provider_error(exc: Exception) -> StandardizedProviderError:
    if isinstance(exc, (TimeoutError, ProviderTimeoutError)):
        return StandardizedProviderError(code="provider_timeout", message="Provider timed out.")
    if isinstance(exc, ProviderAuthenticationError):
        return StandardizedProviderError(code="provider_authentication_failed", message="Provider authentication failed.")
    if isinstance(exc, (ProviderResponseError, ValueError, KeyError, TypeError)):
        return StandardizedProviderError(code="provider_response_invalid", message="Provider response was invalid.")
    return StandardizedProviderError(code="provider_unavailable", message="Provider is unavailable.")
