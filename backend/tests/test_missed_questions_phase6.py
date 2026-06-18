from sqlalchemy import select

from app.domain.enums import MissedQuestionStatus
from app.models.missed_question import MissedQuestion
from app.models.user import User
from app.services.missed_question_service import record_missed_question


def test_record_missed_question_keeps_user_permission_snapshot(db_session) -> None:
    user = User(
        username="snapshot-user",
        password_hash="hash",
        display_name="Snapshot User",
        account_type="full_user",
        content_level="full",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    missed = record_missed_question(db_session, question="No source found", user=user)

    assert missed.question == "No source found"
    assert missed.user_id == user.id
    assert missed.account_type == "full_user"
    assert missed.content_level == "full"
    assert missed.asked_at is not None
    assert missed.status == MissedQuestionStatus.NEW.value


def test_admin_can_list_and_mark_missed_questions_handled(client, admin_headers, general_user_headers, db_session) -> None:
    user = db_session.scalars(select(User).where(User.username == "general-user")).one()
    missed = record_missed_question(db_session, question="Please add this script", user=user)

    listing = client.get("/api/admin/missed-questions", headers=admin_headers)
    handled = client.post(f"/api/admin/missed-questions/{missed.id}/mark-handled", headers=admin_headers)
    denied_list = client.get("/api/admin/missed-questions", headers=general_user_headers)
    denied_update = client.post(f"/api/admin/missed-questions/{missed.id}/mark-handled", headers=general_user_headers)

    assert listing.status_code == 200
    item = listing.json()["items"][0]
    assert item["question"] == "Please add this script"
    assert item["user_id"] == user.id
    assert item["username"] == "general-user"
    assert item["account_type"] == "general_user"
    assert item["content_level"] == "general"
    assert item["status"] == MissedQuestionStatus.NEW.value
    assert handled.status_code == 200
    assert handled.json()["status"] == MissedQuestionStatus.HANDLED.value
    assert handled.json()["handled_at"] is not None
    assert denied_list.status_code == 403
    assert denied_update.status_code == 403

    db_session.refresh(missed)
    assert missed.status == MissedQuestionStatus.HANDLED.value
