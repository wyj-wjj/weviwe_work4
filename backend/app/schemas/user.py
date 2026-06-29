from pydantic import BaseModel, Field, model_validator

from app.domain.enums import AccountType, ContentLevel


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    account_type: AccountType
    content_level: ContentLevel
    department_id: int | None = None

    @model_validator(mode="after")
    def validate_role_level(self) -> "UserCreate":
        if self.account_type == AccountType.GENERAL_USER and self.content_level != ContentLevel.GENERAL:
            raise ValueError("general_user requires general content level")
        if self.account_type == AccountType.FULL_USER and self.content_level != ContentLevel.FULL:
            raise ValueError("full_user requires full content level")
        return self


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    account_type: AccountType | None = None
    content_level: ContentLevel | None = None
    department_id: int | None = None
    is_active: bool | None = None


class UserPasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class UserPublic(BaseModel):
    id: int
    username: str
    display_name: str
    account_type: str
    content_level: str
    department_id: int | None = None
    department_name: str | None = None
