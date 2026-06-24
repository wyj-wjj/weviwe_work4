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


class UpdateLevel(StrEnum):
    MINOR = "minor"
    MEDIUM = "medium"
    MAJOR = "major"


class QuizAction(StrEnum):
    NONE = "none"
    REVIEW_RELATED = "review_related"
    GENERATE_PACK = "generate_pack"


class QuizSourceType(StrEnum):
    MANUAL = "manual"
    AI_GENERATED = "ai_generated"
    AI_ASSISTED = "ai_assisted"


class QuizReviewStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class QuizGenerationStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class QuizSetStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class MissedQuestionStatus(StrEnum):
    NEW = "new"
    HANDLED = "handled"
