"""
Skill: create_mockup
Generate product mockups (framed print, canvas wrap, poster flat lay).

Status: Sprint 3 — not yet implemented.

Three mockups per listing:
  1. Framed print  — white wall, thin black/wood frame (main listing image)
  2. Canvas wrap   — lifestyle living room scene
  3. Poster flat lay — overhead desk scene
"""


def create_mockup(image_path: str, mockup_type: str, output_dir: str) -> dict:
    """Via Placeit API (Sprint 3)."""
    raise NotImplementedError("Mockup creation via Placeit is a Sprint 3 feature.")


def create_mockup_pillow(image_path: str, mockup_type: str, output_dir: str) -> dict:
    """Via custom Pillow templates (Sprint 3 fallback)."""
    raise NotImplementedError("Pillow mockup templates are a Sprint 3 feature.")
