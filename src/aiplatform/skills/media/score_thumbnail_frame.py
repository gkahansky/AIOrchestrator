"""
Platform skill: score_thumbnail_frame

Uses Claude Vision to evaluate candidate frame images and select the best
one for use as a video thumbnail. Venture-agnostic.
"""

import base64
import os
from pathlib import Path

import anthropic


_SYSTEM = """\
You are an expert YouTube/TikTok thumbnail designer who selects the best frame
from a set of video frame candidates. You evaluate frames for:
- Face visibility and expression (engaged, surprised, laughing = good)
- Scene clarity (not blurry, well-lit, uncluttered)
- Visual impact (interesting composition, clear subject)
- Text overlay potential (space for title text overlay)
- Emotional resonance with the clip content

Return ONLY a JSON object with "best_index" (0-based) and "reason" (one sentence). No other text.
"""


def score_thumbnail_frame(
    frame_paths: list[str],
    transcript_chunk: str = "",
    anthropic_api_key: str | None = None,
    model: str = "claude-sonnet-4-6",
) -> dict:
    """
    Select the best thumbnail frame from a list of candidate frame images.

    Args:
        frame_paths:       List of absolute paths to JPEG frame images.
        transcript_chunk:  Text content of the clip (helps Claude pick relevant frame).
        anthropic_api_key: Optional override.
        model:             Claude model to use.

    Returns:
        {
            "best_frame": str,    # path to the selected frame
            "best_index": int,    # 0-based index in frame_paths
            "score": float,       # always 1.0 (binary selection)
            "reason": str,
            "cost_usd": float,
        }
    """
    if not frame_paths:
        raise ValueError("frame_paths must not be empty")

    # If only one frame, return it immediately
    if len(frame_paths) == 1:
        return {
            "best_frame": frame_paths[0],
            "best_index": 0,
            "score": 1.0,
            "reason": "Only one frame available.",
            "cost_usd": 0.0,
        }

    client = anthropic.Anthropic(api_key=anthropic_api_key or os.environ["ANTHROPIC_API_KEY"])

    # Build content blocks: text intro + all frames as base64 images
    # Limit to 8 frames max to control token usage
    candidates = frame_paths[:8]
    content = []

    if transcript_chunk:
        content.append({
            "type": "text",
            "text": f"Clip content: {transcript_chunk[:500]}\n\nEvaluate these {len(candidates)} thumbnail candidates (0-indexed):",
        })
    else:
        content.append({
            "type": "text",
            "text": f"Evaluate these {len(candidates)} thumbnail candidates (0-indexed):",
        })

    for i, fp in enumerate(candidates):
        img_data = Path(fp).read_bytes()
        b64 = base64.standard_b64encode(img_data).decode("utf-8")
        content.append({"type": "text", "text": f"Frame {i}:"})
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        })

    content.append({
        "type": "text",
        "text": 'Return JSON only: {"best_index": <number>, "reason": "<one sentence>"}',
    })

    response = client.messages.create(
        model=model,
        max_tokens=256,
        system=_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )

    import json, re
    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    parsed = json.loads(raw)

    best_index = int(parsed.get("best_index", 0))
    best_index = max(0, min(best_index, len(candidates) - 1))

    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    cost_usd = round(input_tokens * 3e-6 + output_tokens * 15e-6, 4)

    return {
        "best_frame": candidates[best_index],
        "best_index": best_index,
        "score": 1.0,
        "reason": parsed.get("reason", ""),
        "cost_usd": cost_usd,
    }
