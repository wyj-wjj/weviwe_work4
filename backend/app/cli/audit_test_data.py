from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.content import Content, ContentChunk, ContentVersion, VectorIndexRecord
from app.models.missed_question import MissedQuestion
from app.models.quiz import QuizQuestion
from app.models.user import User


_MOJIBAKE_TITLE = re.compile(r"^\?\?8(?:\?|\s|[:：_-])+$")


@dataclass(frozen=True)
class AuditRecord:
    id: int
    label: str
    classification: str


@dataclass(frozen=True)
class AuditReport:
    executed: bool
    contents: tuple[AuditRecord, ...]
    quiz_questions: tuple[AuditRecord, ...]
    users: tuple[AuditRecord, ...]
    detached_quiz_ids: tuple[int, ...] = ()
    detached_missed_question_ids: tuple[int, ...] = ()
    protected_user_ids: tuple[int, ...] = ()


def classify_title(value: str) -> str | None:
    if value.startswith("Phase45 "):
        return "phase45"
    if value.startswith("阶段8手测：") or value.startswith("阶段8手测题"):
        return "phase8"
    if value.startswith("E2E "):
        return "e2e"
    if _MOJIBAKE_TITLE.fullmatch(value):
        return "mojibake"
    return None


def classify_username(value: str) -> str | None:
    if value.startswith("phase45_"):
        return "phase45"
    if value.startswith("phase8_manual_"):
        return "phase8"
    if value.startswith("phase10_"):
        return "e2e"
    return None


def audit_test_data(db: Session, *, execute: bool = False) -> AuditReport:
    contents = tuple(
        AuditRecord(id=content.id, label=content.title, classification=classification)
        for content in db.scalars(select(Content).order_by(Content.id.asc())).all()
        if (classification := classify_title(content.title)) is not None
    )
    quiz_questions = tuple(
        AuditRecord(id=question.id, label=question.question, classification=classification)
        for question in db.scalars(select(QuizQuestion).order_by(QuizQuestion.id.asc())).all()
        if (classification := classify_title(question.question)) is not None
    )
    users = tuple(
        AuditRecord(id=user.id, label=user.username, classification=classification)
        for user in db.scalars(select(User).order_by(User.id.asc())).all()
        if (classification := classify_username(user.username)) is not None
    )

    detached_quiz_ids: tuple[int, ...] = ()
    detached_missed_question_ids: tuple[int, ...] = ()
    protected_user_ids: tuple[int, ...] = ()
    if execute:
        detached_quiz_ids = _delete_classified_content_and_quizzes(
            db,
            content_ids={item.id for item in contents},
            quiz_ids={item.id for item in quiz_questions},
        )
        detached_missed_question_ids, protected_user_ids = _delete_classified_users(
            db,
            user_ids={item.id for item in users},
        )
        db.flush()

    return AuditReport(
        executed=execute,
        contents=contents,
        quiz_questions=quiz_questions,
        users=users,
        detached_quiz_ids=detached_quiz_ids,
        detached_missed_question_ids=detached_missed_question_ids,
        protected_user_ids=protected_user_ids,
    )


def _delete_classified_content_and_quizzes(
    db: Session,
    *,
    content_ids: set[int],
    quiz_ids: set[int],
) -> tuple[int, ...]:
    if quiz_ids:
        matched_questions = db.scalars(
            select(QuizQuestion).where(QuizQuestion.id.in_(quiz_ids))
        ).all()
        for question in matched_questions:
            db.delete(question)
        db.flush()

    detached_quiz_ids: list[int] = []
    if content_ids:
        dependent_questions = db.scalars(
            select(QuizQuestion).where(QuizQuestion.related_content_id.in_(content_ids))
        ).all()
        for question in dependent_questions:
            question.related_content_id = None
            detached_quiz_ids.append(question.id)
        db.flush()

        matched_contents = db.scalars(select(Content).where(Content.id.in_(content_ids))).all()
        for content in matched_contents:
            content.current_version_id = None
        db.flush()

        for model in (VectorIndexRecord, ContentChunk, ContentVersion):
            records = db.scalars(select(model).where(model.content_id.in_(content_ids))).all()
            for record in records:
                db.delete(record)
            db.flush()

        for content in matched_contents:
            db.delete(content)
        db.flush()

    return tuple(sorted(detached_quiz_ids))


def _delete_classified_users(
    db: Session,
    *,
    user_ids: set[int],
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if not user_ids:
        return (), ()

    detached_missed_question_ids: list[int] = []
    missed_questions = db.scalars(
        select(MissedQuestion).where(MissedQuestion.user_id.in_(user_ids))
    ).all()
    for question in missed_questions:
        question.user_id = None
        detached_missed_question_ids.append(question.id)
    db.flush()

    protected_user_ids: list[int] = []
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    for user in users:
        owns_content = db.scalar(select(Content.id).where(Content.created_by == user.id).limit(1))
        owns_version = db.scalar(
            select(ContentVersion.id).where(ContentVersion.created_by == user.id).limit(1)
        )
        if owns_content is not None or owns_version is not None:
            protected_user_ids.append(user.id)
            continue
        db.delete(user)
    db.flush()
    return tuple(sorted(detached_missed_question_ids)), tuple(sorted(protected_user_ids))


def _print_report(report: AuditReport) -> None:
    mode = "EXECUTE" if report.executed else "DRY-RUN"
    print(f"Test data audit mode: {mode}")
    for heading, records in (
        ("contents", report.contents),
        ("quiz_questions", report.quiz_questions),
        ("users", report.users),
    ):
        print(f"{heading}: {len(records)}")
        for record in records:
            print(
                f"  id={record.id} classification={record.classification} "
                f"label={record.label!r}"
            )
    if report.detached_quiz_ids:
        print(f"detached_quiz_ids: {list(report.detached_quiz_ids)}")
    if report.detached_missed_question_ids:
        print(
            "detached_missed_question_ids: "
            f"{list(report.detached_missed_question_ids)}"
        )
    if report.protected_user_ids:
        print(
            "protected_user_ids (retained because they own unclassified data): "
            f"{list(report.protected_user_ids)}"
        )
    if not report.executed:
        print("No rows were changed. Re-run with --execute only after reviewing every record.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit explicitly identified project test data; dry-run by default."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete only classified test records after printing the audit report.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        report = audit_test_data(db, execute=args.execute)
        _print_report(report)
        if args.execute:
            db.commit()
        else:
            db.rollback()


if __name__ == "__main__":
    main()
