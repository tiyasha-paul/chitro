"""Post lifecycle state machine with deterministic transition enforcement."""

from app.domain.enums import PostStatus


class DomainError(Exception):
    """Base error for domain-layer violations."""


class InvalidStateTransitionError(DomainError):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current: PostStatus, target: PostStatus):
        self.current = current
        self.target = target
        super().__init__(
            f"Cannot transition from {current.value!r} to {target.value!r}"
        )


# --- Transition table ---

VALID_TRANSITIONS: dict[PostStatus, set[PostStatus]] = {
    PostStatus.DRAFT: {PostStatus.GENERATED},
    PostStatus.GENERATED: {PostStatus.VALIDATED, PostStatus.VALIDATION_FAILED},
    PostStatus.VALIDATION_FAILED: {PostStatus.GENERATED},
    PostStatus.VALIDATED: {PostStatus.PENDING_APPROVAL},
    PostStatus.PENDING_APPROVAL: {PostStatus.APPROVED, PostStatus.REJECTED},
    PostStatus.APPROVED: {PostStatus.SCHEDULED},
    PostStatus.REJECTED: {PostStatus.GENERATED},
    PostStatus.SCHEDULED: {PostStatus.PUBLISHED},
    PostStatus.PUBLISHED: set(),
}


def validate_transition(current: PostStatus, target: PostStatus) -> None:
    """Raise InvalidStateTransitionError if the transition is not allowed."""
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStateTransitionError(current, target)


def can_transition(current: PostStatus, target: PostStatus) -> bool:
    """Return True if the transition is allowed."""
    return target in VALID_TRANSITIONS.get(current, set())


def get_allowed_transitions(current: PostStatus) -> set[PostStatus]:
    """Return the set of statuses reachable from the current status."""
    return VALID_TRANSITIONS.get(current, set()).copy()


def is_terminal_status(status: PostStatus) -> bool:
    """Return True if no further transitions are possible from this status."""
    return len(VALID_TRANSITIONS.get(status, set())) == 0


def transition_post(post, target: PostStatus) -> None:
    """Validate and apply a status transition on a PlatformPost instance.

    Args:
        post: A PlatformPost instance (or any object with a .status attribute).
        target: The desired new PostStatus.

    Raises:
        InvalidStateTransitionError: If the transition is not allowed.
    """
    current = PostStatus(post.status) if isinstance(post.status, str) else post.status
    validate_transition(current, target)
    post.status = target.value if isinstance(post.status, str) else target
