from pydantic import BaseModel, Field


class RagAskRequest(BaseModel):
    question: str = Field(min_length=1)
