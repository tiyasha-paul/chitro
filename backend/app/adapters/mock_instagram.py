"""Mock Instagram channel adapter for testing and local simulation."""

from datetime import datetime, timezone

from app.adapters.channel import ChannelAdapter, ChannelAdapterError, PublishPayload, PublishResult
from app.domain.enums import Platform
from app.validation.media import ensure_valid_media_asset


class MockInstagramAdapter(ChannelAdapter):
    """Mock Instagram adapter simulating publication without external network calls."""

    def __init__(
        self,
        simulate_failure: bool = False,
        failure_message: str = "Mock Instagram API unreachable",
    ) -> None:
        self.simulate_failure = simulate_failure
        self.failure_message = failure_message
        self.published_calls: list[PublishPayload] = []

    async def publish(self, payload: PublishPayload) -> PublishResult:
        """Simulate publishing an approved post to Instagram."""
        ensure_valid_media_asset(payload.media_spec, Platform.INSTAGRAM)
        if self.simulate_failure:
            raise ChannelAdapterError(self.failure_message, provider="mock_instagram")

        self.published_calls.append(payload)
        external_id = f"mock_ig_{payload.post_id.hex[:12]}"
        now = datetime.now(timezone.utc)
        url = f"https://mock-instagram.chitro.local/p/{external_id}"

        media_format = payload.media_spec["media_type"]

        return PublishResult(
            provider="mock_instagram",
            external_post_id=external_id,
            published_at=now,
            url=url,
            status="published",
            metadata={
                "caption_length": len(payload.caption),
                "media_format": media_format,
                "hashtags_count": len(payload.hashtags) if payload.hashtags else 0,
            },
        )
