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
    assert "先直接回答用户问题" in chat_request["payload"]["messages"][0]["content"]
    assert "关键数字、条件和限制" in chat_request["payload"]["messages"][0]["content"]
    assert "不要机械罗列与问题无关的来源内容" in chat_request["payload"]["messages"][0]["content"]
    assert "开场话术" in chat_request["payload"]["messages"][1]["content"]
    assert "您好，请先说明您的核心需求。" in chat_request["payload"]["messages"][1]["content"]


def test_dashscope_http_client_calls_ocr_model_with_data_url_image() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append({"path": request.url.path, "payload": payload})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "识别出的图片文字"}}]},
        )

    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_base_url="https://dashscope.example/compatible-mode/v1",
        dashscope_ocr_model="qwen-vl-ocr-2025-11-20",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = DashScopeHttpClient(settings, http_client=http_client)
        result = client.ocr_image(image_bytes=b"fake-image", mime_type="image/png")

    assert result == "识别出的图片文字"
    assert requests[0]["path"] == "/compatible-mode/v1/chat/completions"
    assert requests[0]["payload"]["model"] == "qwen-vl-ocr-2025-11-20"
    content = requests[0]["payload"]["messages"][0]["content"]
    assert content[0]["type"] == "image_url"
    assert content[0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_dashscope_http_client_calls_qwen_plus_for_content_import_structure() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append({"path": request.url.path, "payload": payload})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"title": "导入标题"}, ensure_ascii=False),
                        }
                    }
                ]
            },
        )

    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_base_url="https://dashscope.example/compatible-mode/v1",
        dashscope_chat_model="qwen-plus",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = DashScopeHttpClient(settings, http_client=http_client)
        result = client.structure_content_import(
            content_type="standard_script",
            file_name="standard.docx",
            parse_mode="fast",
            raw_text="场景：价格异议",
            warnings=["请核对数字"],
        )

    assert json.loads(result) == {"title": "导入标题"}
    assert requests[0]["path"] == "/compatible-mode/v1/chat/completions"
    assert requests[0]["payload"]["model"] == "qwen-plus"
    assert requests[0]["payload"]["response_format"] == {"type": "json_object"}
    assert "只能基于输入文本整理字段" in requests[0]["payload"]["messages"][0]["content"]
    assert "standard_script" in requests[0]["payload"]["messages"][1]["content"]


def test_dashscope_structure_import_uses_structure_model() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append({"path": request.url.path, "payload": payload})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"title": "Structured"}, ensure_ascii=False),
                        }
                    }
                ]
            },
        )

    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_base_url="https://dashscope.example/compatible-mode/v1",
        dashscope_chat_model="chat-model",
        dashscope_structure_model="structure-model",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = DashScopeHttpClient(settings, http_client=http_client)
        client.structure_content_import(
            content_type="base_script",
            file_name="base.docx",
            parse_mode="fast",
            raw_text="source text",
            warnings=[],
        )

    assert requests[0]["payload"]["model"] == "structure-model"


def test_dashscope_default_http_client_allows_per_request_timeout(monkeypatch) -> None:
    captured_kwargs: list[dict] = []

    class SpyHttpClient:
        def __init__(self, *args, **kwargs) -> None:
            captured_kwargs.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def post(self, _url, *, headers=None, json=None) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("app.integrations.dashscope.httpx.Client", SpyHttpClient)
    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_http_timeout_seconds=8.0,
    )
    client = DashScopeHttpClient(settings)

    response = client._send("/embeddings", {"model": "text-embedding-v4", "input": "test"}, timeout_seconds=60.0)

    assert response.status_code == 200
    assert captured_kwargs == [{"timeout": 60.0, "trust_env": False}]


def test_dashscope_default_http_client_ignores_proxy_environment(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
    captured_kwargs: list[dict] = []

    class SpyHttpClient:
        def __init__(self, *args, **kwargs) -> None:
            captured_kwargs.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def post(self, _url, *, headers=None, json=None) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("app.integrations.dashscope.httpx.Client", SpyHttpClient)
    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_http_timeout_seconds=8.0,
    )
    client = DashScopeHttpClient(settings)

    response = client._send("/embeddings", {"model": "text-embedding-v4", "input": "test"})

    assert response.status_code == 200
    assert captured_kwargs == [{"timeout": 8.0, "trust_env": False}]


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
        client = DashScopeHttpClient(settings, http_client=http_client, sleep=lambda _delay: None)
        with pytest.raises(expected_error):
            client.embed_text("test")


@pytest.mark.parametrize("status_code", [429, 500, 502, 503, 504])
def test_dashscope_retries_temporary_http_status_and_then_succeeds(status_code: int) -> None:
    attempts = 0
    delays: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(status_code, json={"error": {"message": "temporary"}})
        return httpx.Response(
            200,
            json={"model": "text-embedding-v4", "data": [{"embedding": [0.1, 0.2]}]},
        )

    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_base_url="https://dashscope.example/compatible-mode/v1",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = DashScopeHttpClient(settings, http_client=http_client, sleep=delays.append)
        result = client.embed_text("test")

    assert result.vector == [0.1, 0.2]
    assert attempts == 2
    assert delays == [0.2]


@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError])
def test_dashscope_retries_transient_transport_errors_and_then_succeeds(
    error_type: type[httpx.HTTPError],
) -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise error_type("temporary", request=request)
        return httpx.Response(
            200,
            json={"model": "text-embedding-v4", "data": [{"embedding": [0.1, 0.2]}]},
        )

    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_base_url="https://dashscope.example/compatible-mode/v1",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = DashScopeHttpClient(settings, http_client=http_client, sleep=delays.append)
        result = client.embed_text("test")

    assert result.vector == [0.1, 0.2]
    assert attempts == 3
    assert delays == [0.2, 0.4]


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (400, ProviderResponseError),
        (401, ProviderAuthenticationError),
        (403, ProviderAuthenticationError),
        (404, ProviderResponseError),
        (422, ProviderResponseError),
        (501, ProviderResponseError),
    ],
)
def test_dashscope_does_not_retry_permanent_http_statuses(
    status_code: int,
    expected_error: type[Exception],
) -> None:
    attempts = 0
    delays: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status_code, json={"error": {"message": "permanent"}})

    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_base_url="https://dashscope.example/compatible-mode/v1",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = DashScopeHttpClient(settings, http_client=http_client, sleep=delays.append)
        with pytest.raises(expected_error) as exc_info:
            client.embed_text("test")

    assert attempts == 1
    assert delays == []
    assert "test-only-api-key" not in str(exc_info.value)


def test_dashscope_does_not_retry_invalid_json() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, content=b"{", headers={"Content-Type": "application/json"})

    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_base_url="https://dashscope.example/compatible-mode/v1",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = DashScopeHttpClient(settings, http_client=http_client, sleep=delays.append)
        with pytest.raises(ProviderResponseError, match="invalid JSON"):
            client.embed_text("test")

    assert attempts == 1
    assert delays == []


def test_dashscope_stops_after_three_temporary_http_failures() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"error": {"message": "temporary"}})

    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_base_url="https://dashscope.example/compatible-mode/v1",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = DashScopeHttpClient(settings, http_client=http_client, sleep=delays.append)
        with pytest.raises(ProviderResponseError, match="temporary HTTP 503"):
            client.embed_text("test")

    assert attempts == 3
    assert delays == [0.2, 0.4]


def test_dashscope_http_client_standardizes_timeouts_after_three_attempts() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("slow", request=request)

    settings = Settings(
        use_fake_external_clients=False,
        dashscope_api_key="test-only-api-key",
        dashscope_base_url="https://dashscope.example/compatible-mode/v1",
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = DashScopeHttpClient(settings, http_client=http_client, sleep=delays.append)
        with pytest.raises(ProviderTimeoutError):
            client.embed_text("test")

    assert attempts == 3
    assert delays == [0.2, 0.4]
