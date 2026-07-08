from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_dashscope_client, get_milvus_client
from app.db.session import get_db
from app.models.user import User
from app.schemas.rag import RagAskRequest
from app.services.rag_answer_service import answer_question


router = APIRouter(tags=["rag"])


@router.post("/api/app/rag/ask")
def app_ask_rag(
    payload: RagAskRequest,
    current_user: User = Depends(get_current_user),
    debug: bool = Query(default=False),
    db: Session = Depends(get_db),
    dashscope_client=Depends(get_dashscope_client),
    milvus_client=Depends(get_milvus_client),
) -> StreamingResponse:
    generator = answer_question(
        db,
        user=current_user,
        question=payload.question,
        dashscope_client=dashscope_client,
        milvus_client=milvus_client,
        debug=debug,
    )
    return StreamingResponse(generator, media_type="text/event-stream")
