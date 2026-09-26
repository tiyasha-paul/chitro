from enum import Enum


class Platform(str, Enum):
    """Supported social media platforms."""
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    X = "x"


class Language(str, Enum):
    """Supported content languages."""
    BENGALI = "bn"
    ENGLISH = "en"


class PostStatus(str, Enum):
    """Lifecycle status of a platform post."""
    DRAFT = "draft"
    GENERATED = "generated"
    VALIDATED = "validated"
    VALIDATION_FAILED = "validation_failed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
