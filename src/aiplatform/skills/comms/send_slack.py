"""
Skill: send_slack
Post a message to a Slack channel.

Status: Sprint 3 — not yet implemented.
Requires: SLACK_BOT_TOKEN env var.
"""


def send_slack(channel: str, text: str, blocks: list[dict] = None) -> dict:
    """
    Post a message to Slack.

    Returns:
        { ts, channel }
    """
    raise NotImplementedError("send_slack is a Sprint 3 feature.")
