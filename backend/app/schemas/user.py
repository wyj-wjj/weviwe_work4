from pydantic import BaseModel, Field

from app.domain.enums import AccountType, ContentLevel


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    account_type: AccountType
    content_level: ContentLevel


class UserPublic(BaseModel):
    id: int
    username: str
    display_name: str
    account_type: str
    content_level: str
