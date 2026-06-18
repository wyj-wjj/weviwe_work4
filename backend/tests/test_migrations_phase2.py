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
    engine.dispose()


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
