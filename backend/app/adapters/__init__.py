"""Channel publishing adapters package."""

from app.adapters.channel import ChannelAdapter, ChannelAdapterError, PublishPayload, PublishResult
from app.adapters.mock_instagram import MockInstagramAdapter
from app.domain.enums import Platform

_DEFAULT_ADAPTERS: dict[Platform, ChannelAdapter] = {
    Platform.INSTAGRAM: MockInstagramAdapter(),
}


def get_channel_adapter(platform: Platform) -> ChannelAdapter:
    """Resolve channel adapter for the requested platform."""
    adapter = _DEFAULT_ADAPTERS.get(platform)
    if not adapter:
        raise ValueError(f"No publishing adapter configured for platform '{platform.value}'.")
    return adapter


__all__ = [
    "ChannelAdapter",
    "ChannelAdapterError",
    "PublishPayload",
    "PublishResult",
    "MockInstagramAdapter",
    "get_channel_adapter",
]
