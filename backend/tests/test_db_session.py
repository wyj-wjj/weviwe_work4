from sqlalchemy import text

from app.db.session import create_engine_from_url, create_session_factory, session_scope


def test_database_session_scope_commits_and_closes_without_leaking_connection(sqlite_url: str) -> None:
    engine = create_engine_from_url(sqlite_url)
    SessionLocal = create_session_factory(engine)

    with session_scope(SessionLocal) as session:
        session.execute(text("select 1"))
        leased_inside_context = engine.pool.status()

    released_after_context = engine.pool.status()

    assert "checked out" in leased_inside_context.lower()
    assert "checked out" in released_after_context.lower()
    assert "checked out connections: 0" in released_after_context.lower()
    engine.dispose()
