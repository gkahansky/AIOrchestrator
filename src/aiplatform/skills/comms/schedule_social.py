"""
Skill: schedule_social
Queue a social post via Buffer API (Instagram, Facebook).

Status: Sprint 5 — not yet implemented.
Requires: BUFFER_ACCESS_TOKEN env var.
"""


def schedule_social(
    profile_id: str,
    text: str,
    image_path: str = None,
    scheduled_at: str = None,
) -> dict:
    """
    Queue a post in Buffer.

    Args:
        profile_id:   Buffer profile ID for the social channel.
        text:         Post body (caption + hashtags).
        image_path:   Optional local image to attach.
        scheduled_at: ISO 8601 datetime string. If None, adds to queue.

    Returns:
        { update_id, profile_id, scheduled_at }
    """
    raise NotImplementedError("schedule_social is a Sprint 5 feature.")
