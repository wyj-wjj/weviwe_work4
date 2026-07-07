import base64
import json
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
        ocr_text: str = "Fake OCR text.",
        ocr_error: Exception | None = None,
        import_structure: dict[str, Any] | str | None = None,
        import_structure_error: Exception | None = None,
    ) -> None:
        self.chat_answer = chat_answer
        self.embedding = embedding or [0.01, 0.02, 0.03]
        self.embedding_model = embedding_model
        self.embedding_error = embedding_error
        self.chat_error = chat_error
        self.ocr_text = ocr_text
        self.ocr_error = ocr_error
        self.import_structure = import_structure
        self.import_structure_error = import_structure_error
        self.embedding_requests: list[str] = []
        self.chat_requests: list[dict[str, Any]] = []
        self.ocr_requests: list[dict[str, Any]] = []
        self.import_structure_requests: list[dict[str, Any]] = []

    def embed_text(self, text: str) -> EmbeddingResult:
        self.embedding_requests.append(text)
        if self.embedding_error is not None:
            raise self.embedding_error
        return EmbeddingResult(vector=list(self.embedding), model=self.embedding_model)

    def generate_answer(
        self,
        *,
        question: str,
        contexts: list[dict[str, Any]],
        model_name: str | None = None,
        timeout_seconds: float | None = None,
    ) -> ChatGeneration:
        self.chat_requests.append(
            {
                "question": question,
                "contexts": contexts,
                "model_name": model_name,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.chat_error is not None:
            raise self.chat_error
        token_estimate = max(1, sum(len(context.get("text", "")) for context in contexts) // 4)
        return ChatGeneration(
            answer_text=self.chat_answer,
            usage={"prompt_tokens": token_estimate, "completion_tokens": max(1, len(self.chat_answer) // 4)},
        )

    def generate_answer_stream(
        self,
        *,
        question: str,
        contexts: list[dict[str, Any]],
        model_name: str | None = None,
        timeout_seconds: float | None = None,
    ):
        self.chat_requests.append(
            {
                "question": question,
                "contexts": contexts,
                "model_name": model_name,
                "timeout_seconds": timeout_seconds,
                "stream": True,
            }
        )
        if self.chat_error is not None:
            raise self.chat_error
        
        words = self.chat_answer.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")

    def ocr_image(self, *, image_bytes: bytes, mime_type: str) -> str:
        self.ocr_requests.append({"size": len(image_bytes), "mime_type": mime_type})
        if self.ocr_error is not None:
            raise self.ocr_error
        return self.ocr_text

    def structure_content_import(self, **payload: Any) -> str:
        self.import_structure_requests.append(payload)
        if self.import_structure_error is not None:
            raise self.import_structure_error
        if isinstance(self.import_structure, str):
            return self.import_structure
        data = self.import_structure or {
            "title": payload.get("file_name") or "导入草稿",
            "category": "",
            "summary": "",
            "body": payload.get("raw_text") or "",
            "structured_payload": {},
            "warnings": [],
            "split_suggestions": [],
        }
        return json.dumps(data, ensure_ascii=False)


def _chat_content(data: dict[str, Any], *, empty_message: str) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderResponseError("DashScope chat response is missing choices.")
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        parts = [
            str(item.get("text", "")).strip()
            for item in content
            if isinstance(item, dict) and item.get("text")
        ]
        content = "\n".join(part for part in parts if part)
    if not isinstance(content, str) or not content.strip():
        raise ProviderResponseError(empty_message)
    return content.strip()


def _content_import_schema_hint(content_type: str) -> dict[str, Any]:
    if content_type == "standard_script":
        structured_payload = {
            "scene": "",
            "recommended_speech": "",
            "forbidden_speech": "",
            "notes": "",
        }
    elif content_type == "must_read":
        structured_payload = {"update_body": "", "adjustment_points": []}
    else:
        structured_payload = {"points": []}
    return {
        "title": "",
        "category": "",
        "summary": "",
        "body": "",
        "structured_payload": structured_payload,
        "warnings": [],
        "split_suggestions": [],
    }


def _content_import_contract_prompt(content_type: str) -> str:
    shared = (
        "你正在把 Word/PDF 解析文本整理成后台内容草稿。\n"
        "只能基于输入文本整理字段，不得使用外部知识或自行补充业务口径。\n"
        "只允许基于原文整理、概括、分段和抽取字段，不得补充原文没有的业务事实。\n"
        "权限级别、可见范围、部门、生效时间和失效时间由管理员在后台选择，你不能生成或推断这些字段。\n"
        "必须返回合法 JSON，不要返回 Markdown，不要返回解释文本。\n"
    )
    if content_type == "must_read":
        return (
            shared
            + "\n当前内容类型：最新必读 must_read。\n"
            "必须输出字段：\n"
            "- title: 适合作为更新标题的短标题。\n"
            "- category: 从原文归纳的分类；不确定时返回空字符串。\n"
            "- summary: 120 个中文字符以内，概括本次更新影响。\n"
            "- body: 保留换行的正文。\n"
            "- structured_payload.update_body: 保留格式的更新正文。\n"
            "- structured_payload.adjustment_points: 调整要点数组；没有明确要点时返回空数组。\n"
            "不要返回 split_suggestions，最新必读不自动拆分。\n"
        )
    if content_type == "base_script":
        return (
            shared
            + "\n当前内容类型：核心基础话术 base_script。\n"
            "必须输出字段：\n"
            "- title: 适合作为基础话术的短标题。\n"
            "- category: 从原文归纳的分类；不确定时返回空字符串。\n"
            "- summary: 120 个中文字符以内，概括话术核心价值。\n"
            "- body: 保留换行的完整基础话术正文。\n"
            "- structured_payload.points: 核心要点数组；没有明确要点时返回空数组。\n"
            "不要返回 split_suggestions，核心基础话术不自动拆分。\n"
        )
    return (
        shared
        + "\n当前内容类型：标准化话术 standard_script。\n"
        "单条草稿必须输出字段：\n"
        "- title: 文档级标题。\n"
        "- category: 从原文归纳的分类；不确定时返回空字符串。\n"
        "- summary: 120 个中文字符以内，概括文档内容。\n"
        "- body: 整理后的正文。\n"
        "- structured_payload.scene: 如果全文只有一个明确场景，则填写；否则返回空字符串。\n"
        "- structured_payload.recommended_speech: 如果全文只有一条明确推荐话术，则填写；否则返回空字符串。\n"
        "- structured_payload.forbidden_speech: 原文明确禁止或不建议说法。\n"
        "- structured_payload.notes: 注意事项。\n\n"
        "拆分规则：\n"
        "拆分标准化话术时，每个 split_suggestion 必须是一个可独立保存的话术条目。\n"
        "每个 split_suggestion 必须有 title、summary、body、structured_payload.scene、structured_payload.recommended_speech。\n"
        "如果某一段无法生成“场景”和“推荐说法”，不要把它作为可保存拆解候选。\n"
        "forbidden_speech 和 notes 没有原文依据时可以返回空字符串，但不能编造。\n"
        "章节标题属于其后内容，不能放在上一条候选正文末尾。\n"
        "若文档是产品介绍、培训讲稿或知识文章，而不是多条标准话术，请返回 single_draft，并将 split_suggestions 置为空。\n"
        "不要为了凑数量拆分。\n"
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

    def _send(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> httpx.Response:
        url = f"{self.settings.dashscope_base_url.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
        }
        if self.http_client is not None:
            return self.http_client.post(url, headers=headers, json=payload)
        timeout = timeout_seconds or self.settings.dashscope_http_timeout_seconds
        with httpx.Client(timeout=timeout, trust_env=False) as client:
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

    def _post_json(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        for attempt in range(MAX_HTTP_ATTEMPTS):
            try:
                response = self._send(path, payload, timeout_seconds=timeout_seconds)
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

    def generate_answer(
        self,
        *,
        question: str,
        contexts: list[dict[str, Any]],
        model_name: str | None = None,
        timeout_seconds: float | None = None,
    ) -> ChatGeneration:
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
                "model": model_name or self.settings.dashscope_chat_model,
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
            timeout_seconds=timeout_seconds,
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

    def generate_answer_stream(
        self,
        *,
        question: str,
        contexts: list[dict[str, Any]],
        model_name: str | None = None,
        timeout_seconds: float | None = None,
    ):
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

        payload = {
            "model": model_name or self.settings.dashscope_chat_model,
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
            "stream": True,
            "stream_options": {"include_usage": True}
        }
        
        url = f"{self.settings.dashscope_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.dashscope_api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        timeout = timeout_seconds or self.settings.dashscope_http_timeout_seconds
        
        try:
            with httpx.Client(timeout=timeout, trust_env=False) as client:
                with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        raise ProviderResponseError(f"DashScope returned HTTP {response.status_code}.")
                    for line in response.iter_lines():
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if not data_str or data_str == "[DONE]":
                                continue
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if choices and "delta" in choices[0]:
                                    content = choices[0]["delta"].get("content")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            raise ProviderTimeoutError("DashScope streaming request timed out or could not connect.") from exc
        except httpx.HTTPError as exc:
            raise ProviderResponseError("DashScope streaming request failed.") from exc

    def ocr_image(self, *, image_bytes: bytes, mime_type: str) -> str:
        image_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        data = self._post_json(
            "/chat/completions",
            {
                "model": self.settings.dashscope_ocr_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_url}},
                            {
                                "type": "text",
                                "text": "请只识别图片中的文字，按自然阅读顺序输出，不要解释。",
                            },
                        ],
                    }
                ],
                "stream": False,
            },
            timeout_seconds=self.settings.dashscope_ocr_timeout_seconds,
        )
        return _chat_content(data, empty_message="DashScope OCR response contains no text.")

    def structure_content_import(self, **payload: Any) -> str:
        content_type = payload.get("content_type")
        raw_text = payload.get("raw_text")
        warnings = payload.get("warnings") or []
        schema_hint = _content_import_schema_hint(str(content_type))
        contract_prompt = _content_import_contract_prompt(str(content_type))
        data = self._post_json(
            "/chat/completions",
            {
                "model": self.settings.dashscope_structure_model,
                "messages": [
                    {
                        "role": "system",
                        "content": contract_prompt,
                    },
                    {
                        "role": "user",
                        "content": (
                            f"内容类型：{content_type}\n"
                            f"文件名：{payload.get('file_name')}\n"
                            f"解析模式：{payload.get('parse_mode')}\n"
                            f"解析警告：{warnings}\n"
                            f"目标 JSON schema：{schema_hint}\n\n"
                            f"原文：\n{raw_text}"
                        ),
                    },
                ],
                "stream": False,
                "response_format": {"type": "json_object"},
            },
            timeout_seconds=self.settings.dashscope_import_timeout_seconds,
        )
        return _chat_content(data, empty_message="DashScope structure response contains no JSON text.")


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
