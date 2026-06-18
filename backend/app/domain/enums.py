from enum import StrEnum


class AccountType(StrEnum):
    ADMIN = "admin"
    FULL_USER = "full_user"
    GENERAL_USER = "general_user"


class ContentLevel(StrEnum):
    GENERAL = "general"
    FULL = "full"


class ContentType(StrEnum):
    BASE_SCRIPT = "base_script"
    STANDARD_SCRIPT = "standard_script"
    MUST_READ = "must_read"


class ContentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    OFFLINE = "offline"


class IndexStatus(StrEnum):
    NOT_SYNCED = "not_synced"
    SYNCED = "synced"
    FAILED = "failed"


class QuestionStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class MissedQuestionStatus(StrEnum):
    NEW = "new"
    HANDLED = "handled"
