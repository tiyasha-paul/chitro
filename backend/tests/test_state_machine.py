import pytest
from types import SimpleNamespace
from app.domain.enums import PostStatus
from app.domain.state_machine import (
    VALID_TRANSITIONS,
    InvalidStateTransitionError,
    can_transition,
    get_allowed_transitions,
    is_terminal_status,
    transition_post,
    validate_transition,
)

# 1. Parametrized test for ALL 10 valid transitions
@pytest.mark.parametrize(
    "current, target",
    [
        (PostStatus.DRAFT, PostStatus.GENERATED),
        (PostStatus.GENERATED, PostStatus.VALIDATED),
        (PostStatus.GENERATED, PostStatus.VALIDATION_FAILED),
        (PostStatus.VALIDATION_FAILED, PostStatus.GENERATED),
        (PostStatus.VALIDATED, PostStatus.PENDING_APPROVAL),
        (PostStatus.PENDING_APPROVAL, PostStatus.APPROVED),
        (PostStatus.PENDING_APPROVAL, PostStatus.REJECTED),
        (PostStatus.APPROVED, PostStatus.SCHEDULED),
        (PostStatus.REJECTED, PostStatus.GENERATED),
        (PostStatus.SCHEDULED, PostStatus.PUBLISHED),
    ],
)
def test_valid_transitions(current: PostStatus, target: PostStatus) -> None:
    # 3. Test can_transition returns True for valid
    validate_transition(current, target)  # Should not raise
    assert can_transition(current, target) is True


# 2. Parametrized test for invalid transitions
@pytest.mark.parametrize(
    "current, target",
    [
        (PostStatus.DRAFT, PostStatus.PUBLISHED),
        (PostStatus.DRAFT, PostStatus.APPROVED),
        (PostStatus.DRAFT, PostStatus.SCHEDULED),
        (PostStatus.DRAFT, PostStatus.VALIDATED),
        (PostStatus.DRAFT, PostStatus.PENDING_APPROVAL),
        (PostStatus.GENERATED, PostStatus.PENDING_APPROVAL),
        (PostStatus.GENERATED, PostStatus.APPROVED),
        (PostStatus.GENERATED, PostStatus.PUBLISHED),
        (PostStatus.VALIDATION_FAILED, PostStatus.VALIDATED),
        (PostStatus.VALIDATION_FAILED, PostStatus.APPROVED),
        (PostStatus.VALIDATION_FAILED, PostStatus.PUBLISHED),
        (PostStatus.VALIDATED, PostStatus.APPROVED),
        (PostStatus.VALIDATED, PostStatus.PUBLISHED),
        (PostStatus.APPROVED, PostStatus.PUBLISHED),
        (PostStatus.PUBLISHED, PostStatus.DRAFT),
        (PostStatus.PUBLISHED, PostStatus.GENERATED),
    ],
)
def test_invalid_transitions(current: PostStatus, target: PostStatus) -> None:
    # 3. Test can_transition returns False for invalid
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(current, target)
    assert can_transition(current, target) is False


# 4. Test get_allowed_transitions returns correct sets for each status
def test_get_allowed_transitions() -> None:
    assert get_allowed_transitions(PostStatus.DRAFT) == {PostStatus.GENERATED}
    assert get_allowed_transitions(PostStatus.GENERATED) == {PostStatus.VALIDATED, PostStatus.VALIDATION_FAILED}
    assert get_allowed_transitions(PostStatus.PUBLISHED) == set()


# 5. Test is_terminal_status: only PUBLISHED is terminal
def test_is_terminal_status() -> None:
    for status in PostStatus:
        if status == PostStatus.PUBLISHED:
            assert is_terminal_status(status) is True
        else:
            assert is_terminal_status(status) is False


# 6. Test transition_post with a mock object
def test_transition_post_success() -> None:
    post = SimpleNamespace(status=PostStatus.DRAFT)
    transition_post(post, PostStatus.GENERATED)
    assert post.status == PostStatus.GENERATED.value


# 7. Test transition_post raises InvalidStateTransitionError for invalid transitions
def test_transition_post_failure() -> None:
    post = SimpleNamespace(status=PostStatus.DRAFT)
    with pytest.raises(InvalidStateTransitionError):
        transition_post(post, PostStatus.PUBLISHED)


# 8. Test that every PostStatus appears in VALID_TRANSITIONS as a key
def test_all_statuses_in_transitions() -> None:
    for status in PostStatus:
        assert status in VALID_TRANSITIONS


# 9. Test InvalidStateTransitionError attributes (current, target)
def test_error_attributes() -> None:
    error = InvalidStateTransitionError(PostStatus.DRAFT, PostStatus.PUBLISHED)
    assert error.current == PostStatus.DRAFT
    assert error.target == PostStatus.PUBLISHED


# 10. Test error message format
def test_error_message() -> None:
    error = InvalidStateTransitionError(PostStatus.DRAFT, PostStatus.PUBLISHED)
    assert str(error) == "Cannot transition from 'draft' to 'published'"
