"""Domain-level exceptions for Chitro."""

from app.domain.enums import PostStatus


class DomainError(Exception):
    """Base exception for all domain violations."""


class ResourceNotFoundError(DomainError):
    """Raised when an entity (Campaign, PlatformPost, etc.) cannot be found."""

    def __init__(self, resource_type: str, identifier: str):
        self.resource_type = resource_type
        self.identifier = identifier
        super().__init__(f"{resource_type} with ID '{identifier}' not found.")


class InvalidStateTransitionError(DomainError):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current: PostStatus, target: PostStatus):
        self.current = current
        self.target = target
        super().__init__(
            f"Cannot transition from {current.value!r} to {target.value!r}"
        )
