"""Seed local data for Phase 8 frontend manual testing.

This script is intentionally a development helper. It reads credentials from
environment variables and does not contain real database passwords or API keys.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

from sqlalchemy import select

from app.core.security import hash_password, verify_password
from app.db.session import session_scope
from app.domain.enums import AccountType, ContentLevel, ContentStatus, ContentType, QuestionStatus
from app.models.content import Content
from app.models.quiz import QuizQuestion
from app.models.user import User
from app.schemas.content import ContentCreate, ContentUpdate
from app.services.content_service import create_content, publish_content, update_content


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def upsert_user(
    *,
    db,
    username: str,
    password: str,
    display_name: str,
    account_type: AccountType,
    content_level: ContentLevel,
) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            account_type=account_type.value,
            content_level=content_level.value,
            is_active=True,
        )
        db.add(user)
    else:
        if not verify_password(password, user.password_hash):
            user.password_hash = hash_password(password)
        user.display_name = display_name
        user.account_type = account_type.value
        user.content_level = content_level.value
        user.is_active = True
    db.flush()
    return user


def sample_contents() -> Iterable[ContentCreate]:
    yield ContentCreate(
        content_type=ContentType.MUST_READ,
        title="阶段8手测：新版产品介绍口径",
        category="产品更新",
        permission_level=ContentLevel.GENERAL,
        summary="最新必读测试内容",
        body="新版产品介绍需要先确认客户背景，再说明适用边界。",
        structured_payload={
            "update_body": "介绍新版产品时，先确认客户使用场景，再说明服务范围和合规边界。",
            "adjustment_points": ["先问场景再介绍", "禁止承诺固定收益", "必要时转交主管复核"],
        },
    )
    yield ContentCreate(
        content_type=ContentType.BASE_SCRIPT,
        title="阶段8手测：基础开场白",
        category="开场",
        permission_level=ContentLevel.GENERAL,
        summary="基础话术测试内容",
        body="您好，我会先确认您的业务场景，再根据已发布口径说明适用方案。",
        structured_payload={"points": ["确认客户身份", "确认业务场景", "说明服务边界"]},
    )
    yield ContentCreate(
        content_type=ContentType.STANDARD_SCRIPT,
        title="阶段8手测：风险提示标准话术",
        category="风控",
        permission_level=ContentLevel.GENERAL,
        summary="标准话术测试内容",
        body="风险提示标准话术正文。",
        structured_payload={
            "scene": "客户询问高风险方案时",
            "recommended_speech": "建议先说明风险等级、适用条件和无法保证结果的边界。",
            "forbidden_speech": "不能承诺收益，不能淡化风险。",
            "notes": "客户持续追问收益承诺时转交主管。",
        },
    )
    yield ContentCreate(
        content_type=ContentType.STANDARD_SCRIPT,
        title="阶段8手测：全量权限专属话术",
        category="全量场景",
        permission_level=ContentLevel.FULL,
        summary="全量权限测试内容",
        body="全量权限员工可见的话术正文。电池循环寿命标准口径为 6000-8000 次。",
        structured_payload={
            "scene": "全量权限客户深度沟通",
            "recommended_speech": "根据当前全量材料，电池循环寿命标准口径为 6000-8000 次。",
            "forbidden_speech": "不能向通用权限员工或客户泄露内部全量材料。",
            "notes": "用于验证 general_user 不可见、full_user 可见。",
        },
    )


def publish_sample_content(*, db, admin: User) -> dict[str, Content]:
    result: dict[str, Content] = {}
    for payload in sample_contents():
        content = db.scalar(select(Content).where(Content.title == payload.title))
        if content is None:
            content = create_content(db, creator=admin, payload=payload)
            needs_publish = True
        else:
            if content.content_type != payload.content_type.value:
                raise RuntimeError(
                    f"Stable seed title has a different content type: {payload.title}"
                )
            needs_publish = not published_snapshot_matches(content, payload)
            if content.status == ContentStatus.OFFLINE.value:
                content.status = ContentStatus.DRAFT.value
                db.commit()
            content = update_content(
                db,
                content_id=content.id,
                payload=ContentUpdate(
                    title=payload.title,
                    category=payload.category,
                    permission_level=payload.permission_level,
                    summary=payload.summary,
                    body=payload.body,
                    structured_payload=payload.structured_payload,
                ),
            )

        if needs_publish:
            publish_content(db, content_id=content.id)
            content = db.get(Content, content.id)
        if content is None:
            raise RuntimeError(f"Failed to create content: {payload.title}")
        result[content.title] = content
    db.flush()
    return result


def published_snapshot_matches(content: Content, payload: ContentCreate) -> bool:
    version = content.current_version
    if version is None or content.status != ContentStatus.PUBLISHED.value:
        return False
    version_permission = getattr(version, "permission_level", content.permission_level)
    return (
        content.content_type == payload.content_type.value
        and content.category == payload.category
        and content.permission_level == payload.permission_level.value
        and version.title == payload.title
        and version.summary == payload.summary
        and version.body == payload.body
        and version.structured_payload == payload.structured_payload
        and version_permission == payload.permission_level.value
    )


def ensure_quiz_questions(
    *,
    db,
    general_related_content_id: int,
    full_related_content_id: int,
) -> None:
    for seed in quiz_question_seeds(
        general_related_content_id=general_related_content_id,
        full_related_content_id=full_related_content_id,
    ):
        question = db.scalar(
            select(QuizQuestion).where(QuizQuestion.question == seed["question"])
        )
        legacy_question = seed.get("legacy_question")
        if question is None and legacy_question:
            question = db.scalar(
                select(QuizQuestion).where(QuizQuestion.question == legacy_question)
            )
        if question is None:
            question = QuizQuestion(question=seed["question"])
            db.add(question)
        question.question = seed["question"]
        question.options = seed["options"]
        question.answer = seed["answer"]
        question.explanation = seed["explanation"]
        question.related_content_id = seed["related_content_id"]
        question.permission_level = seed["permission_level"]
        question.status = QuestionStatus.ENABLED.value
    db.flush()


def quiz_question_seeds(
    *,
    general_related_content_id: int,
    full_related_content_id: int,
) -> list[dict[str, object]]:
    general_questions = [
        {
            "question": f"阶段8手测题 {index}：遇到收益承诺请求时应该怎么做？",
            "options": ["说明风险边界", "承诺固定收益", "忽略客户问题"],
            "answer": "说明风险边界",
            "explanation": "标准口径要求先说明风险等级、适用条件和无法保证结果的边界。",
            "related_content_id": general_related_content_id,
            "permission_level": ContentLevel.GENERAL.value,
        }
        for index in range(1, 5)
    ]
    return [
        *general_questions,
        {
            "question": "阶段8手测题 5：根据全量材料，电池循环寿命的标准口径是什么？",
            "legacy_question": "阶段8手测题 5：遇到收益承诺请求时应该怎么做？",
            "options": ["6000-8000 次", "100-200 次", "没有任何限制"],
            "answer": "6000-8000 次",
            "explanation": "该数字来自全量权限专属话术，仅用于 full_user 权限验证。",
            "related_content_id": full_related_content_id,
            "permission_level": ContentLevel.FULL.value,
        },
    ]


def main() -> None:
    password = required_env("WEVIEW_MANUAL_PASSWORD")
    with session_scope() as db:
        admin = upsert_user(
            db=db,
            username="phase8_manual_admin",
            password=password,
            display_name="阶段8手测管理员",
            account_type=AccountType.ADMIN,
            content_level=ContentLevel.FULL,
        )
        upsert_user(
            db=db,
            username="phase8_manual_general",
            password=password,
            display_name="阶段8通用员工",
            account_type=AccountType.GENERAL_USER,
            content_level=ContentLevel.GENERAL,
        )
        upsert_user(
            db=db,
            username="phase8_manual_full",
            password=password,
            display_name="阶段8全量员工",
            account_type=AccountType.FULL_USER,
            content_level=ContentLevel.FULL,
        )
        contents = publish_sample_content(db=db, admin=admin)
        ensure_quiz_questions(
            db=db,
            general_related_content_id=contents["阶段8手测：风险提示标准话术"].id,
            full_related_content_id=contents["阶段8手测：全量权限专属话术"].id,
        )

    print("Phase 8 manual seed data is ready.")
    print("Users: phase8_manual_general, phase8_manual_full, phase8_manual_admin")


if __name__ == "__main__":
    main()
