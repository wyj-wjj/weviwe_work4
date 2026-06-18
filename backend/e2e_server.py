import os
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent
DATABASE_PATH = BACKEND_ROOT / "tmp" / "phase10-e2e.db"
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

os.environ["DATABASE_URL"] = f"sqlite:///{DATABASE_PATH.as_posix()}"
os.environ["JWT_SECRET_KEY"] = "phase10-e2e-only-secret-with-32-plus-characters"
os.environ["USE_FAKE_EXTERNAL_CLIENTS"] = "true"
os.environ["RAG_SIMILARITY_THRESHOLD"] = "0.7"

import uvicorn

from app.api.deps import get_dashscope_client, get_milvus_client
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.e2e_fixture import build_e2e_clients, seed_e2e_fixture
from app.main import app


def prepare_e2e_application() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    dashscope_client, milvus_client = build_e2e_clients()
    with SessionLocal() as session:
        seed_e2e_fixture(
            session,
            dashscope_client=dashscope_client,
            milvus_client=milvus_client,
        )
    app.dependency_overrides[get_dashscope_client] = lambda: dashscope_client
    app.dependency_overrides[get_milvus_client] = lambda: milvus_client


if __name__ == "__main__":
    prepare_e2e_application()
    uvicorn.run(
        app,
        host=os.getenv("E2E_BACKEND_HOST", "127.0.0.1"),
        port=int(os.getenv("E2E_BACKEND_PORT", "8010")),
        log_level="warning",
    )
