from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.domain.enums import ContentStatus
from app.integrations.dashscope import normalize_provider_error
from app.models.content import ContentChunk
from app.models.user import User
from app.services.content_service import visible_levels_for
from app.services.missed_question_service import record_missed_question


MISSED_MESSAGE = "当前没有有效标准口径，请联系管理员。"
QUERY_EXPANSIONS = (
    (("电池能用多少次", "能循环多少次"), "电池循环寿命 充放电循环次数"),
)
RELATIVE_SCORE_WINDOW = 0.12


def retrieval_question(question: str) -> str:
    normalized = question.strip()
    for phrases, expansion in QUERY_EXPANSIONS:
        if any(phrase in normalized for phrase in phrases):
            return f"{normalized} {expansion}"
    return normalized


def provider_unavailable(exc: Exception) -> AppError:
    provider_error = normalize_provider_error(exc)
    return AppError(
        code="ai_unavailable",
        message="智能问答暂不可用，请稍后重试。",
        status_code=503,
        details={"provider_error": provider_error.code},
    )


def source_from_chunk(chunk: ContentChunk, *, relevance_score: float) -> dict[str, Any]:
    version = chunk.version
    content = chunk.content
    return {
        "content_id": content.id,
        "version_id": version.id,
        "chunk_id": chunk.id,
        "title": version.title,
        "content_type": content.content_type,
        "updated_at": version.published_at,
        "relevance_score": relevance_score,
    }


def load_authorized_contexts(
    db: Session,
    *,
    hits,
    user: User,
    min_score: float,
) -> list[dict[str, Any]]:
    allowed_levels = visible_levels_for(user)
    contexts: list[dict[str, Any]] = []
    contexts_by_content_id: dict[int, dict[str, Any]] = {}
    seen_texts_by_content_id: dict[int, set[str]] = {}
    seen_chunk_ids: set[int] = set()
    best_authorized_score: float | None = None
    for hit in sorted(hits, key=lambda item: item.score, reverse=True):
        if hit.score < min_score:
            continue
        chunk_id = hit.metadata.get("chunk_id")
        if not isinstance(chunk_id, int) or chunk_id in seen_chunk_ids:
            continue
        chunk = db.get(ContentChunk, chunk_id)
        if chunk is None or not chunk.is_active:
            continue
        content = chunk.content
        if (
            content.status != ContentStatus.PUBLISHED.value
            or content.current_version_id != chunk.version_id
            or content.permission_level not in allowed_levels
            or chunk.permission_level not in allowed_levels
        ):
            continue
        if best_authorized_score is None:
            best_authorized_score = hit.score
        if hit.score < best_authorized_score - RELATIVE_SCORE_WINDOW:
            continue

        existing_context = contexts_by_content_id.get(content.id)
        if existing_context is None:
            existing_context = {
                "text": chunk.chunk_text,
                "source": source_from_chunk(chunk, relevance_score=hit.score),
            }
            contexts_by_content_id[content.id] = existing_context
            seen_texts_by_content_id[content.id] = {chunk.chunk_text}
            contexts.append(existing_context)
        elif chunk.chunk_text not in seen_texts_by_content_id[content.id]:
            existing_context["text"] = f"{existing_context['text']}\n\n{chunk.chunk_text}"
            seen_texts_by_content_id[content.id].add(chunk.chunk_text)
        seen_chunk_ids.add(chunk.id)
    return contexts


def answer_question(
    db: Session,
    *,
    user: User,
    question: str,
    dashscope_client,
    milvus_client,
    settings: Settings | None = None,
) -> dict[str, Any]:
    resolved_settings = settings or Settings()
    try:
        question_embedding = dashscope_client.embed_text(retrieval_question(question))
        hits = milvus_client.search(
            resolved_settings.milvus_collection_name,
            query_vector=question_embedding.vector,
            allowed_permission_levels=visible_levels_for(user),
            top_k=resolved_settings.rag_top_k,
        )
    except Exception as exc:
        raise provider_unavailable(exc) from exc

    contexts = load_authorized_contexts(
        db,
        hits=hits,
        user=user,
        min_score=resolved_settings.rag_similarity_threshold,
    )
    if not contexts:
        record_missed_question(db, question=question, user=user)
        return {"hit": False, "answer": MISSED_MESSAGE, "sources": []}

    chat_contexts = [
        {
            "text": context["text"],
            "source": context["source"],
        }
        for context in contexts
    ]
    try:
        answer = dashscope_client.generate_answer(question=question, contexts=chat_contexts)
    except Exception as exc:
        raise provider_unavailable(exc) from exc

    return {
        "hit": True,
        "answer": answer.answer_text,
        "sources": [context["source"] for context in contexts],
        "usage": answer.usage,
    }
