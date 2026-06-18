from fastapi import FastAPI

from app.api.routes import admin, auth, content, missed_question, quiz, rag, user
from app.core.config import Settings
from app.core.errors import register_exception_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    app = FastAPI(title="WeView Work4 MVP API")
    register_exception_handlers(app)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.include_router(content.router)
    app.include_router(quiz.router)
    app.include_router(rag.router)
    app.include_router(missed_question.router)
    app.include_router(user.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": resolved_settings.service_name,
        }

    return app


app = create_app()
