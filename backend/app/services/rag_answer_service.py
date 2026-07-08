import json
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.enums import ContentStatus
from app.integrations.milvus import MilvusSearchHit
from app.models.content import Content, ContentChunk, ContentVersion
from app.models.user import User
from app.services.permission_service import can_view_all_department_scopes, scope_filter, scope_is_visible, visible_levels_for
from app.services.missed_question_service import record_missed_question


MISSED_MESSAGE = "当前没有有效标准口径，请联系管理员。"
QUERY_EXPANSIONS = (
    (("电池能用多少次", "能循环多少次"), "电池循环寿命 充放电循环次数"),
    (("项目环境影响", "环境影响", "环评"), "储能项目环境影响评价 环评 合规 噪声 危废 防火间距"),
)
KEYWORD_SEARCH_BASE_SCORE = 0.55
KEYWORD_SEARCH_MAX_SCORE = 0.75
KEYWORD_SEARCH_FETCH_MULTIPLIER = 10
KEYWORD_SEARCH_MIN_TERM_MATCHES = 2
KEYWORD_STOP_WORDS: frozenset[str] = frozenset({
    # structural particles
    "的", "了", "是", "在", "有", "和", "就", "都",
    "也", "还", "但", "而", "与", "从", "到", "对",
    "向", "比", "用", "给", "被", "把", "让", "叫",
    "因", "为", "所", "以", "可", "能", "会", "着",
    "过", "则", "若", "且", "非", "不",
    # question / generic words
    "怎么", "如何", "什么", "哪些", "怎么样", "怎么办",
    "为什么", "之所以", "多少", "多长", "多重", "多宽",
    "多高", "多久", "多大", "哪里", "哪个", "哪种",
    "可否", "能否",
    # common filler
    "相关", "话术", "标准", "内容", "资料", "口径",
    "要求", "客户", "项目", "一下", "请问",
    # single chars that jieba may still emit
    "？", "?", "，", ",", "。", ".", "、",
    "：", ":", "；", ";", "！", "!",
})
KEYWORD_EXPANSIONS = (
    (("消防", "灭火", "烟感", "温感"), ("消防", "消防配置", "消防验收", "消防安全", "烟感", "温感", "气体灭火", "消防报告", "保险")),
    (("并网",), ("并网", "并网接入", "接入流程", "并网验收", "电网公司", "并网周期")),
    (("环评", "环境影响"), ("环评", "环境影响", "环境影响评价", "合规", "噪声", "危废", "防火间距")),
    (("技术参数", "电芯", "PCS", "BMS"), ("技术参数", "电芯", "LFP", "磷酸铁锂", "钠离子", "液流电池", "PCS", "BMS")),
    (("投资", "回报", "回收周期", "收益"), ("投资回报", "回收周期", "收益", "峰谷价差", "投资收益")),
    (("电价", "峰谷", "电费"), ("电价", "分时电价", "峰谷", "电费账单")),
    (("补贴",), ("补贴", "申报", "额度", "政策")),
    (("巡检", "故障", "应急"), ("巡检", "故障", "应急", "BMS通讯", "PCS过温")),
    (("合同", "质保", "条款"), ("合同", "质保", "条款", "谈判")),
    (("施工", "安装", "进场", "运输"), ("施工", "安装", "进场", "运输", "现场准备")),
)


def retrieval_question(question: str) -> str:
    normalized = question.strip()
    for phrases, expansion in QUERY_EXPANSIONS:
        if any(phrase in normalized for phrase in phrases):
            return f"{normalized} {expansion}"
    return normalized


def keyword_terms_for_question(question: str) -> list[str]:
    import jieba

    normalized = question.strip()
    terms: list[str] = []

    # 1. Domain synonym expansion (KEYWORD_EXPANSIONS)
    for triggers, expansion_terms in KEYWORD_EXPANSIONS:
        if any(trigger in normalized for trigger in triggers):
            terms.extend(expansion_terms)

    # 2. jieba segmentation → filter stop words → keep ≥ 2 chars
    words = [w.strip() for w in jieba.cut(normalized) if len(w.strip()) >= 2]
    terms.extend(w for w in words if w not in KEYWORD_STOP_WORDS)

    # 3. Deduplicate, prefer longer terms first
    unique_terms: list[str] = []
    seen: set[str] = set()
    for term in sorted((t.strip() for t in terms), key=len, reverse=True):
        if term and term not in seen:
            seen.add(term)
            unique_terms.append(term)
    return unique_terms


def keyword_match_score(chunk: ContentChunk, *, terms: list[str], question: str) -> tuple[float, int]:
    title = chunk.version.title or ""
    category = chunk.content.category or ""
    text = chunk.chunk_text or ""
    matched_terms = 0
    weighted_score = 0.0
    for term in terms:
        term_score = 0.0
        if term in title:
            term_score += 0.15
        if category and term in category:
            term_score += 0.10
        if term in text:
            term_score += 0.05
        if term_score:
            matched_terms += 1
            weighted_score += min(term_score, 0.20)
    if matched_terms == 0:
        return 0.0, 0

    if "话术" in question and chunk.content.content_type in {"base_script", "standard_script"}:
        weighted_score += 0.03
    if any(len(term) >= 4 and (term in title or term in text) for term in terms):
        weighted_score += 0.02
    return min(KEYWORD_SEARCH_MAX_SCORE, KEYWORD_SEARCH_BASE_SCORE + weighted_score + matched_terms * 0.01), matched_terms


def keyword_search_hits(
    db: Session,
    *,
    question: str,
    user: User,
    top_k: int,
) -> list[MilvusSearchHit]:
    terms = keyword_terms_for_question(question)
    if not terms:
        return []
    allowed_levels = visible_levels_for(user)
    term_conditions = []
    for term in terms:
        term_conditions.extend(
            [
                ContentVersion.title.contains(term),
                Content.category.contains(term),
                ContentChunk.chunk_text.contains(term),
            ]
        )
    stmt = (
        select(ContentChunk)
        .join(Content, ContentChunk.content_id == Content.id)
        .join(ContentVersion, ContentChunk.version_id == ContentVersion.id)
        .where(Content.status == ContentStatus.PUBLISHED.value)
        .where(Content.current_version_id == ContentChunk.version_id)
        .where(Content.permission_level.in_(allowed_levels))
        .where(ContentChunk.permission_level.in_(allowed_levels))
        .where(scope_filter(user, Content))
        .where(scope_filter(user, ContentChunk))
        .where(ContentChunk.is_active.is_(True))
        .where(or_(*term_conditions))
        .order_by(ContentChunk.id.asc())
        .limit(max(top_k * KEYWORD_SEARCH_FETCH_MULTIPLIER, top_k))
    )
    scored_hits: list[MilvusSearchHit] = []
    for chunk in db.scalars(stmt).all():
        score, matched = keyword_match_score(chunk, terms=terms, question=question)
        if score <= 0 or matched < KEYWORD_SEARCH_MIN_TERM_MATCHES:
            continue
        scored_hits.append(
            MilvusSearchHit(
                primary_key=f"keyword-{chunk.id}",
                score=score,
                metadata={
                    "content_id": chunk.content_id,
                    "version_id": chunk.version_id,
                    "chunk_id": chunk.id,
                    "permission_level": chunk.permission_level,
                    "scope_type": chunk.scope_type,
                    "department_id": chunk.department_id,
                    "is_active": chunk.is_active,
                    "retrieval_path": "keyword",
                },
            )
        )
    return sorted(scored_hits, key=lambda hit: hit.score, reverse=True)[:top_k]


VECTOR_RESULT_SLOTS = 6
KEYWORD_RESULT_SLOTS = 4


def interleave_retrieval_hits(
    vector_hits: list[MilvusSearchHit],
    keyword_hits: list[MilvusSearchHit],
) -> list[MilvusSearchHit]:
    """Slot-based interleaving: vector first, keyword second, dedup by chunk_id."""
    vec_sorted = sorted(vector_hits, key=lambda h: h.score, reverse=True)
    kw_sorted = sorted(keyword_hits, key=lambda h: h.score, reverse=True)

    seen_chunk_ids: set[int] = set()
    interleaved: list[MilvusSearchHit] = []

    for hit in vec_sorted[:VECTOR_RESULT_SLOTS]:
        chunk_id = hit.metadata.get("chunk_id")
        if isinstance(chunk_id, int):
            seen_chunk_ids.add(chunk_id)
        interleaved.append(hit)

    for hit in kw_sorted:
        if len(interleaved) >= VECTOR_RESULT_SLOTS + KEYWORD_RESULT_SLOTS:
            break
        chunk_id = hit.metadata.get("chunk_id")
        if isinstance(chunk_id, int) and chunk_id in seen_chunk_ids:
            continue
        if isinstance(chunk_id, int):
            seen_chunk_ids.add(chunk_id)
        interleaved.append(hit)

    return interleaved


def source_from_chunk(chunk: ContentChunk, *, relevance_score: float) -> dict[str, Any]:
    version = chunk.version
    content = chunk.content
    return {
        "content_id": content.id,
        "version_id": version.id,
        "chunk_id": chunk.id,
        "title": version.title,
        "content_type": content.content_type,
        "scope_type": content.scope_type,
        "department_id": content.department_id,
        "department_name": content.department.name if content.department else None,
        "updated_at": version.published_at,
        "update_level": version.update_level,
        "relevance_score": relevance_score,
    }


def adjacent_authorized_chunks(db: Session, *, chunk: ContentChunk, user: User) -> list[ContentChunk]:
    allowed_levels = visible_levels_for(user)
    stmt = (
        select(ContentChunk)
        .where(ContentChunk.content_id == chunk.content_id)
        .where(ContentChunk.version_id == chunk.version_id)
        .where(ContentChunk.is_active.is_(True))
        .where(ContentChunk.sort_order.in_([chunk.sort_order - 1, chunk.sort_order, chunk.sort_order + 1]))
        .order_by(ContentChunk.sort_order.asc(), ContentChunk.id.asc())
    )
    chunks = []
    for candidate in db.scalars(stmt).all():
        if (
            candidate.permission_level in allowed_levels
            and scope_is_visible(user, candidate.scope_type, candidate.department_id)
        ):
            chunks.append(candidate)
    return chunks


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
    for hit in hits:
        if hit.score < min_score:
            continue
        chunk_id = hit.metadata.get("chunk_id")
        if not isinstance(chunk_id, int):
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
            or not scope_is_visible(user, content.scope_type, content.department_id)
            or not scope_is_visible(user, chunk.scope_type, chunk.department_id)
        ):
            continue

        existing_context = contexts_by_content_id.get(content.id)
        
        if chunk_id in seen_chunk_ids:
            if existing_context is not None:
                if chunk.chunk_text not in existing_context.get("hit_texts", []):
                    existing_context.setdefault("hit_texts", []).append(chunk.chunk_text)
            continue

        context_chunks = adjacent_authorized_chunks(db, chunk=chunk, user=user)

        if existing_context is None:
            context_text = "\n\n".join(candidate.chunk_text for candidate in context_chunks)
            existing_context = {
                "text": context_text,
                "source": source_from_chunk(chunk, relevance_score=hit.score),
                "hit_texts": [chunk.chunk_text],
            }
            contexts_by_content_id[content.id] = existing_context
            seen_texts_by_content_id[content.id] = {candidate.chunk_text for candidate in context_chunks}
            contexts.append(existing_context)
        else:
            existing_context["hit_texts"].append(chunk.chunk_text)
            for context_chunk in context_chunks:
                if context_chunk.chunk_text not in seen_texts_by_content_id[content.id]:
                    existing_context["text"] = f"{existing_context['text']}\n\n{context_chunk.chunk_text}"
                    seen_texts_by_content_id[content.id].add(context_chunk.chunk_text)
        seen_chunk_ids.update(candidate.id for candidate in context_chunks)
    return contexts


def answer_question(
    db: Session,
    *,
    user: User,
    question: str,
    dashscope_client,
    milvus_client,
    settings: Settings | None = None,
    debug: bool = False,
):
    resolved_settings = settings or Settings()

    # ---------- debug: log terms ----------
    if debug:
        import jieba  # noqa: F811
        raw_terms = [w for w in jieba.cut(question.strip()) if len(w.strip()) >= 2]
        clean_terms = keyword_terms_for_question(question)
        yield f"data: {json.dumps({'type': 'debug', 'stage': 'terms', 'raw_jieba': raw_terms, 'final_terms': clean_terms})}\n\n"

    try:
        expanded_q = retrieval_question(question)
        question_embedding = dashscope_client.embed_text(expanded_q)
        vector_hits = milvus_client.search(
            resolved_settings.milvus_collection_name,
            query_vector=question_embedding.vector,
            allowed_permission_levels=visible_levels_for(user),
            visible_department_id=user.department_id,
            include_all_department_scoped=can_view_all_department_scopes(user),
            top_k=resolved_settings.rag_top_k,
        )
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': '智能问答暂不可用，请稍后重试。'})}\n\n"
        return

    # ---------- debug: vector hits ----------
    if debug:
        vec_hits_debug = [{"chunk_id": h.metadata.get("chunk_id"), "score": round(h.score, 4), "path": "vector"} for h in vector_hits]
        yield f"data: {json.dumps({'type': 'debug', 'stage': 'vector_hits', 'count': len(vector_hits), 'hits': vec_hits_debug})}\n\n"

    keyword_hits = keyword_search_hits(
        db,
        question=question,
        user=user,
        top_k=resolved_settings.rag_top_k,
    )

    # ---------- debug: keyword hits ----------
    if debug:
        kw_hits_debug = [{"chunk_id": h.metadata.get("chunk_id"), "score": round(h.score, 4), "path": "keyword"} for h in keyword_hits]
        yield f"data: {json.dumps({'type': 'debug', 'stage': 'keyword_hits', 'count': len(keyword_hits), 'hits': kw_hits_debug})}\n\n"

    hits = interleave_retrieval_hits(vector_hits, keyword_hits)

    # ---------- debug: merged hits ----------
    if debug:
        merged_debug = [{"chunk_id": h.metadata.get("chunk_id"), "score": round(h.score, 4), "path": h.metadata.get("retrieval_path", "vector")} for h in hits]
        yield f"data: {json.dumps({'type': 'debug', 'stage': 'merged_hits', 'count': len(hits), 'hits': merged_debug})}\n\n"

    contexts = load_authorized_contexts(
        db,
        hits=hits,
        user=user,
        min_score=resolved_settings.rag_similarity_threshold,
    )

    # ---------- debug: final contexts ----------
    if debug:
        ctx_debug = [{
            "chunk_id": c["source"].get("chunk_id"),
            "content_id": c["source"].get("content_id"),
            "title": c["source"].get("title"),
            "score": c["source"].get("relevance_score"),
            "text_preview": c["text"][:200] if c.get("text") else "(empty)",
        } for c in contexts]
        yield f"data: {json.dumps({'type': 'debug', 'stage': 'contexts', 'threshold': resolved_settings.rag_similarity_threshold, 'count': len(contexts), 'contexts': ctx_debug}, default=str, ensure_ascii=False)}\n\n"

    if not contexts:
        record_missed_question(db, question=question, user=user)
        yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
        yield f"data: {json.dumps({'type': 'content', 'text': MISSED_MESSAGE})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    sources = [context["source"] for context in contexts]
    yield f"data: {json.dumps({'type': 'sources', 'sources': sources}, default=str)}\n\n"

    try:
        for chunk in dashscope_client.generate_answer_stream(
            question=question,
            contexts=contexts,
        ):
            yield f"data: {json.dumps({'type': 'content', 'text': chunk})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': '生成回答时发生错误，请稍后重试。'})}\n\n"
        return
        
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
