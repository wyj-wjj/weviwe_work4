import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings


class ProviderConfigurationError(RuntimeError):
    pass


class ProviderTimeoutError(RuntimeError):
    pass


class ProviderAuthenticationError(RuntimeError):
    pass


class ProviderResponseError(RuntimeError):
    pass


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_HTTP_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 0.2


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
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.http_client = http_client
        self.sleep = sleep

    def _send(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        url = f"{self.settings.dashscope_base_url.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        if self.http_client is not None:
            return self.http_client.post(url, headers=headers, json=payload)
        with httpx.Client(timeout=self.settings.dashscope_http_timeout_seconds, trust_env=False) as client:
            return client.post(url, headers=headers, json=payload)

    @staticmethod
    def _decode_response(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderResponseError("DashScope returned invalid JSON.") from exc
        if not isinstance(data, dict):
            raise ProviderResponseError("DashScope returned an invalid response object.")
        return data

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(MAX_HTTP_ATTEMPTS):
            try:
                response = self._send(path, payload)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                if attempt == MAX_HTTP_ATTEMPTS - 1:
                    raise ProviderTimeoutError("DashScope request timed out or could not connect.") from exc
                self.sleep(RETRY_BASE_DELAY_SECONDS * (2**attempt))
                continue
            except httpx.HTTPError as exc:
                raise ProviderResponseError("DashScope request failed.") from exc

            if response.status_code in {401, 403}:
                raise ProviderAuthenticationError("DashScope authentication failed.")
            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt == MAX_HTTP_ATTEMPTS - 1:
                    raise ProviderResponseError(
                        f"DashScope returned temporary HTTP {response.status_code}."
                    )
                self.sleep(RETRY_BASE_DELAY_SECONDS * (2**attempt))
                continue
            if response.status_code >= 400:
                raise ProviderResponseError(f"DashScope returned HTTP {response.status_code}.")
            return self._decode_response(response)
        raise ProviderResponseError("DashScope retry loop exhausted.")

    def embed_text(self, text: str) -> EmbeddingResult:
        data = self._post_json(
            "/embeddings",
            {
                "model": self.settings.dashscope_embedding_model,
                "input": text,
                "encoding_format": "float",
            },
        )
        items = data.get("data")
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            raise ProviderResponseError("DashScope embedding response is missing data.")
        vector = items[0].get("embedding")
        if not isinstance(vector, list) or not vector or not all(isinstance(value, (int, float)) for value in vector):
            raise ProviderResponseError("DashScope embedding response contains an invalid vector.")
        model = data.get("model") or self.settings.dashscope_embedding_model
        if not isinstance(model, str):
            raise ProviderResponseError("DashScope embedding response contains an invalid model name.")
        return EmbeddingResult(vector=[float(value) for value in vector], model=model)

    def generate_answer(self, *, question: str, contexts: list[dict[str, Any]]) -> ChatGeneration:
        source_blocks = []
        for index, context in enumerate(contexts, start=1):
            source = context.get("source") if isinstance(context.get("source"), dict) else {}
            title = source.get("title") or f"来源 {index}"
            text = context.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            source_blocks.append(f"[来源 {index}] {title}\n{text.strip()}")
        if not source_blocks:
            raise ProviderResponseError("No authorized context was provided for answer generation.")

        data = self._post_json(
            "/chat/completions",
            {
                "model": self.settings.dashscope_chat_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是企业官方话术助手。只能依据提供的已授权来源回答，"
                            "不得补充来源中没有的业务结论，不得推测，不得泄露未提供的内容。"
                            "先直接回答用户问题，并覆盖来源中与问题直接相关的关键数字、条件和限制。"
                            "不要机械罗列与问题无关的来源内容。"
                            "如果来源不足以回答，应明确说明现有来源不足。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"用户问题：{question}\n\n"
                            "以下内容均已通过当前账号权限和有效状态校验：\n\n"
                            + "\n\n".join(source_blocks)
                        ),
                    },
                ],
                "stream": False,
            },
        )
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderResponseError("DashScope chat response is missing choices.")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError("DashScope chat response contains no answer text.")
        raw_usage = data.get("usage")
        usage = (
            {key: int(value) for key, value in raw_usage.items() if isinstance(value, (int, float))}
            if isinstance(raw_usage, dict)
            else {}
        )
        return ChatGeneration(answer_text=content.strip(), usage=usage)


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
