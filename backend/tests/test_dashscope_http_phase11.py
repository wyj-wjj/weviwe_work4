import json

import httpx
import pytest

from app.core.config import Settings
from app.integrations.dashscope import (
    DashScopeHttpClient,
    ProviderAuthenticationError,
    ProviderResponseError,
    ProviderTimeoutError,
)


def test_dashscope_http_client_calls_openai_compatible_embedding_and_chat() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(
            {
                "path": request.url.path,
                "authorization": request.headers.get("Authorization"),
                "payload": payload,
            }
        )
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(
                200,
                json={
                    "model": "text-embedding-v4",
                    "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}],
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": "仅使用授权来源回答。"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
            },
        )

    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_base_url="https://dashscope.example/compatible-mode/v1",
        dashscope_chat_model="qwen-plus",
        dashscope_embedding_model="text-embedding-v4",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = DashScopeHttpClient(settings, http_client=http_client)
        embedding = client.embed_text("客户开场怎么说？")
        answer = client.generate_answer(
            question="客户开场怎么说？",
            contexts=[
                {
                    "text": "您好，请先说明您的核心需求。",
                    "source": {"content_id": 1, "title": "开场话术"},
                }
            ],
        )

    assert embedding.vector == [0.1, 0.2, 0.3]
    assert embedding.model == "text-embedding-v4"
    assert answer.answer_text == "仅使用授权来源回答。"
    assert answer.usage == {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18}

    embedding_request, chat_request = requests
    assert embedding_request == {
        "path": "/compatible-mode/v1/embeddings",
        "authorization": "Bearer test-only-api-key",
        "payload": {
            "model": "text-embedding-v4",
            "input": "客户开场怎么说？",
            "encoding_format": "float",
        },
    }
    assert chat_request["path"] == "/compatible-mode/v1/chat/completions"
    assert chat_request["authorization"] == "Bearer test-only-api-key"
    assert chat_request["payload"]["model"] == "qwen-plus"
    assert chat_request["payload"]["stream"] is False
    assert "只能依据提供的已授权来源" in chat_request["payload"]["messages"][0]["content"]
    assert "开场话术" in chat_request["payload"]["messages"][1]["content"]
    assert "您好，请先说明您的核心需求。" in chat_request["payload"]["messages"][1]["content"]


@pytest.mark.parametrize(
    ("response", "expected_error"),
    [
        (httpx.Response(401, json={"error": {"message": "bad key"}}), ProviderAuthenticationError),
        (httpx.Response(500, json={"error": {"message": "provider down"}}), ProviderResponseError),
        (httpx.Response(200, json={"data": []}), ProviderResponseError),
    ],
)
def test_dashscope_http_client_standardizes_http_and_payload_errors(
    response: httpx.Response,
    expected_error: type[Exception],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return response

    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_base_url="https://dashscope.example/compatible-mode/v1",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = DashScopeHttpClient(settings, http_client=http_client)
        with pytest.raises(expected_error):
            client.embed_text("test")


def test_dashscope_http_client_standardizes_timeouts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_base_url="https://dashscope.example/compatible-mode/v1",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = DashScopeHttpClient(settings, http_client=http_client)
        with pytest.raises(ProviderTimeoutError):
            client.embed_text("test")
