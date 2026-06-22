from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


ROOT = Path(__file__).resolve().parents[1]


def make_alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_alembic_upgrade_creates_required_tables_and_constraints(sqlite_url: str) -> None:
    command.upgrade(make_alembic_config(sqlite_url), "head")

    engine = create_engine(sqlite_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert {
        "users",
        "contents",
        "content_versions",
        "content_chunks",
        "vector_index_records",
        "quiz_questions",
        "missed_questions",
    } <= tables

    assert "conversation_threads" not in tables
    assert "conversation_messages" not in tables
    assert "rag_answer_sources" not in tables
    assert "quiz_attempts" not in tables
    assert "quiz_scores" not in tables

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    assert {
        "username",
        "password_hash",
        "display_name",
        "account_type",
        "content_level",
        "is_active",
        "created_at",
        "updated_at",
    } <= user_columns

    unique_constraints = inspector.get_unique_constraints("users")
    assert any(constraint["column_names"] == ["username"] for constraint in unique_constraints)

    content_columns = {column["name"]: column for column in inspector.get_columns("contents")}
    assert {"draft_revision", "published_draft_revision"} <= set(content_columns)
    assert content_columns["draft_revision"]["nullable"] is False

    version_columns = {column["name"]: column for column in inspector.get_columns("content_versions")}
    assert "permission_level" in version_columns
    assert version_columns["permission_level"]["nullable"] is False
    with engine.connect() as connection:
        revision = connection.execute(text("select version_num from alembic_version")).scalar_one()
    assert len(revision) <= 32
    engine.dispose()


def test_publish_revision_migration_backfills_existing_rows_and_can_downgrade(sqlite_url: str) -> None:
    config = make_alembic_config(sqlite_url)
    command.upgrade(config, "0003_add_content_index_status")

    engine = create_engine(sqlite_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                insert into users (
                    id, username, password_hash, display_name, account_type,
                    content_level, is_active, created_at, updated_at
                ) values (
                    1, 'migration-admin', 'hash', '迁移管理员', 'admin',
                    'full', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.execute(
            text(
                """
                insert into contents (
                    id, content_type, title, category, permission_level, status,
                    current_version_id, created_by, created_at, updated_at,
                    draft_summary, draft_body, draft_payload, index_status
                ) values (
                    1, 'base_script', '历史内容', '接待', 'full', 'published',
                    null, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
                    '摘要', '正文', null, 'synced'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                insert into content_versions (
                    id, content_id, version_no, title, summary, body,
                    structured_payload, published_at, effective_at, expired_at,
                    created_by, created_at
                ) values (
                    1, 1, 1, '历史内容', '摘要', '正文',
                    null, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, null,
                    1, CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.execute(text("update contents set current_version_id = 1 where id = 1"))
    engine.dispose()

    command.upgrade(config, "head")

    upgraded_engine = create_engine(sqlite_url)
    with upgraded_engine.connect() as connection:
        content_row = connection.execute(
            text(
                """
                select draft_revision, published_draft_revision
                from contents where id = 1
                """
            )
        ).one()
        version_permission = connection.execute(
            text("select permission_level from content_versions where id = 1")
        ).scalar_one()
    assert content_row.draft_revision == 1
    assert content_row.published_draft_revision == 1
    assert version_permission == "full"
    upgraded_engine.dispose()

    command.downgrade(config, "0003_add_content_index_status")

    downgraded_engine = create_engine(sqlite_url)
    downgraded_inspector = inspect(downgraded_engine)
    assert "draft_revision" not in {
        column["name"] for column in downgraded_inspector.get_columns("contents")
    }
    assert "published_draft_revision" not in {
        column["name"] for column in downgraded_inspector.get_columns("contents")
    }
    assert "permission_level" not in {
        column["name"] for column in downgraded_inspector.get_columns("content_versions")
    }
    downgraded_engine.dispose()


def test_alembic_can_downgrade_to_base_without_orphaning_version_rows(sqlite_url: str) -> None:
    config = make_alembic_config(sqlite_url)
    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(sqlite_url)
    inspector = inspect(engine)

    if "alembic_version" in inspector.get_table_names():
        with engine.connect() as connection:
            version_rows = connection.execute(text("select count(*) from alembic_version")).scalar_one()
        assert version_rows == 0
    engine.dispose()


def test_default_alembic_config_uses_database_url_environment(
    sqlite_url: str,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", sqlite_url)
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))

    command.upgrade(config, "head")

    engine = create_engine(sqlite_url)
    assert "users" in inspect(engine).get_table_names()
    engine.dispose()
