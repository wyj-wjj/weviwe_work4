from typing import Any

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domain.enums import AccountType, ContentLevel, ContentType, QuestionStatus
from app.integrations.dashscope import EmbeddingResult, FakeDashScopeClient
from app.integrations.milvus import FakeMilvusClient
from app.models.user import User
from app.schemas.content import ContentCreate
from app.schemas.quiz import QuizQuestionCreate
from app.services.content_service import create_content, publish_content
from app.services.quiz_service import create_quiz_question
from app.services.rag_index_service import sync_content_index


E2E_ADMIN_USERNAME = "phase10_admin"
E2E_FULL_USERNAME = "phase10_full"
E2E_GENERAL_USERNAME = "phase10_general"
E2E_PASSWORD = "Phase10-E2E-Password!"
E2E_MISS_QUESTION = "E2E_MISS_这是一个确定性未命中问题"
E2E_CHAT_ANSWER = "E2E 回答：请使用已发布且当前账号可见的标准话术。"


class E2EDashScopeClient(FakeDashScopeClient):
    def __init__(self) -> None:
        super().__init__(
            chat_answer=E2E_CHAT_ANSWER,
            embedding=[1.0, 0.0, 0.0],
            embedding_model="phase10-e2e-embedding",
        )

    def embed_text(self, text: str) -> EmbeddingResult:
        if text == E2E_MISS_QUESTION:
            self.embedding_requests.append(text)
            return EmbeddingResult(vector=[-1.0, 0.0, 0.0], model=self.embedding_model)
        return super().embed_text(text)


def build_e2e_clients() -> tuple[E2EDashScopeClient, FakeMilvusClient]:
    return E2EDashScopeClient(), FakeMilvusClient()


def create_e2e_user(
    db: Session,
    *,
    username: str,
    display_name: str,
    account_type: AccountType,
    content_level: ContentLevel,
) -> User:
    user = User(
        username=username,
        password_hash=hash_password(E2E_PASSWORD),
        display_name=display_name,
        account_type=account_type.value,
        content_level=content_level.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def content_fixture_payloads() -> list[ContentCreate]:
    return [
        ContentCreate(
            content_type=ContentType.MUST_READ,
            title="E2E 通用最新必读",
            category="E2E 更新",
            permission_level=ContentLevel.GENERAL,
            summary="通用最新必读摘要",
            body="通用员工需要阅读的最新口径。",
            structured_payload={
                "update_body": "通用员工需要阅读的最新口径。",
                "adjustment_points": ["先确认客户需求", "只使用已发布口径"],
            },
        ),
        ContentCreate(
            content_type=ContentType.MUST_READ,
            title="E2E 全量最新必读",
            category="E2E 更新",
            permission_level=ContentLevel.FULL,
            summary="全量最新必读摘要",
            body="仅完整权限员工可见的最新口径。",
            structured_payload={
                "update_body": "仅完整权限员工可见的最新口径。",
                "adjustment_points": ["不得向通用权限账号展示"],
            },
        ),
        ContentCreate(
            content_type=ContentType.BASE_SCRIPT,
            title="E2E 通用基础话术",
            category="E2E 开场",
            permission_level=ContentLevel.GENERAL,
            summary="通用开场要点",
            body="您好，请先说明您的核心需求，我们会依据正式口径为您介绍。",
            structured_payload={"points": ["确认需求", "依据正式口径"]},
        ),
        ContentCreate(
            content_type=ContentType.BASE_SCRIPT,
            title="E2E 全量基础话术",
            category="E2E 全量",
            permission_level=ContentLevel.FULL,
            summary="全量权限要点",
            body="这是仅完整权限员工可使用的内部完整口径。",
            structured_payload={"points": ["仅限完整权限员工"]},
        ),
        ContentCreate(
            content_type=ContentType.STANDARD_SCRIPT,
            title="E2E 通用标准话术",
            category="E2E 风险",
            permission_level=ContentLevel.GENERAL,
            summary="通用风险提示",
            body="请明确说明信息以正式发布内容为准。",
            structured_payload={
                "scene": "客户询问风险",
                "recommended_speech": "相关信息请以公司正式发布的有效口径为准。",
                "forbidden_speech": "不要承诺未发布的信息。",
                "notes": "保持客观，不扩展原文。",
            },
        ),
        ContentCreate(
            content_type=ContentType.STANDARD_SCRIPT,
            title="E2E 全量标准话术",
            category="E2E 全量",
            permission_level=ContentLevel.FULL,
            summary="全量权限标准话术",
            body="仅完整权限员工可使用的标准表达。",
            structured_payload={
                "scene": "完整权限场景",
                "recommended_speech": "这是完整权限范围内的标准表达。",
                "forbidden_speech": "不得向通用权限员工透露。",
                "notes": "严格校验账号权限。",
            },
        ),
    ]


def seed_e2e_fixture(
    db: Session,
    *,
    dashscope_client: E2EDashScopeClient,
    milvus_client: FakeMilvusClient,
) -> dict[str, Any]:
    admin = create_e2e_user(
        db,
        username=E2E_ADMIN_USERNAME,
        display_name="阶段十管理员",
        account_type=AccountType.ADMIN,
        content_level=ContentLevel.FULL,
    )
    create_e2e_user(
        db,
        username=E2E_FULL_USERNAME,
        display_name="阶段十完整权限员工",
        account_type=AccountType.FULL_USER,
        content_level=ContentLevel.FULL,
    )
    create_e2e_user(
        db,
        username=E2E_GENERAL_USERNAME,
        display_name="阶段十通用权限员工",
        account_type=AccountType.GENERAL_USER,
        content_level=ContentLevel.GENERAL,
    )

    contents = []
    for payload in content_fixture_payloads():
        content = create_content(db, creator=admin, payload=payload)
        publish_content(db, content_id=content.id)
        sync_result = sync_content_index(
            db,
            content_id=content.id,
            dashscope_client=dashscope_client,
            milvus_client=milvus_client,
        )
        if sync_result.status != "synced":
            raise RuntimeError(f"Failed to index E2E content {content.id}: {sync_result.error_code}")
        db.refresh(content)
        contents.append(content)

    for index in range(1, 6):
        create_quiz_question(
            db,
            QuizQuestionCreate(
                question=f"E2E 通用题目 {index}",
                options=["A", "B"],
                answer="A",
                explanation=f"E2E 通用题目解析 {index}",
                related_content_id=contents[2].id,
                permission_level=ContentLevel.GENERAL,
                status=QuestionStatus.ENABLED,
            ),
        )
    create_quiz_question(
        db,
        QuizQuestionCreate(
            question="E2E 全量题目",
            options=["A", "B"],
            answer="A",
            explanation="E2E 全量题目解析",
            related_content_id=contents[3].id,
            permission_level=ContentLevel.FULL,
            status=QuestionStatus.ENABLED,
        ),
    )

    return {
        "user_count": 3,
        "content_count": len(contents),
        "quiz_count": 6,
        "content_ids": {content.title: content.id for content in contents},
    }
