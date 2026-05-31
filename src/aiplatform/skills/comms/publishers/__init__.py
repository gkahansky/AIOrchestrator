"""
Publish handlers — one module per social platform.

Mirrors the `senders/` registry pattern. Each handler exposes:
    publish(req: PublishRequest, config: dict) -> PublishResult

Resolve a platform to its handler via the registry:
    from aiplatform.skills.comms.publishers import HANDLERS
    result = HANDLERS["linkedin_page"].publish(req, config)

Channels with no native-API token configured fall back to assisted-send
(deep link + manual confirm). Adding a platform = one handler file + one
entry in the dict below.
"""
from aiplatform.skills.comms.publishers import (
    linkedin_page,
    facebook_page,
    instagram_business,
    youtube_channel,
)

HANDLERS = {
    "linkedin_page":      linkedin_page,
    "facebook_page":      facebook_page,
    "instagram_business": instagram_business,
    "youtube_channel":    youtube_channel,
}

VALID_PUBLISH_CHANNELS = set(HANDLERS.keys())
