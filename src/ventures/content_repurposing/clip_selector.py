"""
Content Repurposing — clip selection logic.

Takes raw virality-scored windows, applies threshold filtering,
deduplicates overlapping windows, and returns top N per plan.
"""

from ventures.content_repurposing.config import VIRALITY_SCORE_THRESHOLD


def select_clips(scored_windows: list[dict], plan: str, plans: dict) -> list[dict]:
    """
    Filter and rank clip windows for the given plan.

    Args:
        scored_windows: Output from score_clip_virality — list of
                        {start_s, end_s, score, hook, reason, transcript_chunk}.
        plan:           Customer plan key (e.g. "starter").
        plans:          The PLANS dict from config.

    Returns:
        Filtered and ranked list of clip dicts, length <= plans[plan]["clips"].
    """
    plan_cfg = plans.get(plan, plans["starter"])
    max_clips = plan_cfg["clips"]

    # 1. Apply score threshold
    above_threshold = [
        w for w in scored_windows
        if float(w.get("score", 0)) >= VIRALITY_SCORE_THRESHOLD
    ]

    # If nothing survives the threshold, take the top candidates anyway
    if not above_threshold:
        above_threshold = sorted(
            scored_windows,
            key=lambda w: float(w.get("score", 0)),
            reverse=True,
        )[:max_clips]

    # 2. Sort by score descending
    ranked = sorted(above_threshold, key=lambda w: float(w.get("score", 0)), reverse=True)

    # 3. Deduplicate overlapping windows (>50% overlap → keep higher score)
    selected: list[dict] = []
    for candidate in ranked:
        if len(selected) >= max_clips:
            break
        c_start = float(candidate["start_s"])
        c_end = float(candidate["end_s"])
        c_dur = c_end - c_start

        overlap_found = False
        for existing in selected:
            e_start = float(existing["start_s"])
            e_end = float(existing["end_s"])
            overlap = max(0.0, min(c_end, e_end) - max(c_start, e_start))
            if c_dur > 0 and overlap / c_dur > 0.5:
                overlap_found = True
                break

        if not overlap_found:
            selected.append(candidate)

    return selected
