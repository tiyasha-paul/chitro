"""Domain-level exceptions for Chitro."""

from app.domain.state_machine import DomainError, InvalidStateTransitionError


class ResourceNotFoundError(DomainError):
    """Raised when an entity (Campaign, PlatformPost, etc.) cannot be found."""

    def __init__(self, resource_type: str, identifier: str):
        self.resource_type = resource_type
        self.identifier = identifier
        super().__init__(f"{resource_type} with ID '{identifier}' not found.")


class PostNotPublishedError(DomainError):
    """Raised when attempting to record metrics on a non-published post."""

    def __init__(self, post_id: str, current_status: str):
        self.post_id = post_id
        self.current_status = current_status
        super().__init__(
            f"Cannot record metrics for post '{post_id}' in status '{current_status}'. Post must be published."
        )


class CitationValidationError(DomainError):
    """Raised when an AI-generated report contains invalid or unsupported citations."""
