"""
Skill: create_pin
Create a Pinterest pin for a product listing.

Status: Sprint 5 — not yet implemented.
Requires: PINTEREST_ACCESS_TOKEN, PINTEREST_BOARD_ID env vars.
Note: Pinterest API review takes 1–2 weeks — apply during Sprint 1.
"""


def create_pin(
    image_path: str,
    title: str,
    description: str,
    link: str,
    board_id: str = None,
) -> dict:
    """
    Create a Pinterest pin.

    Returns:
        { pin_id, url }
    """
    raise NotImplementedError("create_pin is a Sprint 5 feature.")
