"""Quality gate — AI-tell critic, length checks, banned-phrase filter.

Runs after item generation, before status flips to `review_pending`. Produces
a structured `quality_report_json` blob the review UI renders inline so the
human reviewer sees exactly which spans look AI-generated and can edit them
in place.

Calls Claude Sonnet 4.6 for the critic pass. The deterministic checks (length,
banned phrases) run locally with no API cost.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from ventures.content_engine.config import CHANNEL_LENGTH_BUDGETS
from ventures.content_engine.prompts import critic_system_prompt


# ── Deterministic checks ──────────────────────────────────────────────────────

def find_banned_phrases(text: str, banned: list[str]) -> list[str]:
    """Lowercase substring match. Returns the list of banned phrases found."""
    if not text or not banned:
        return []
    lowered = text.lower()
    return [phrase for phrase in banned if phrase.lower() in lowered]


def check_length(text: str, channel: str) -> dict[str, Any]:
    """Length budget check per channel. Returns {ok, chars, min, max}."""
    budget = CHANNEL_LENGTH_BUDGETS.get(channel)
    if not budget:
        return {"ok": True, "chars": len(text or ""), "min": None, "max": None}
    n = len(text or "")
    return {
        "ok":   budget["min_chars"] <= n <= budget["max_chars"],
        "chars": n,
        "min":  budget["min_chars"],
        "max":  budget["max_chars"],
    }


_EM_DASH_RE = re.compile(r"[—–]|--")


def em_dash_density(text: str) -> float:
    """Em-dashes per 100 words. >1.25 is a meaningful AI-tell signal."""
    words = max(1, len((text or "").split()))
    dashes = len(_EM_DASH_RE.findall(text or ""))
    return round(dashes * 100.0 / words, 3)


# ── Claude critic ─────────────────────────────────────────────────────────────

def run_ai_tell_critic(text: str) -> dict[str, Any]:
    """Score a draft 0–100 for human-readability. Returns the critic JSON.

    Degrades to a neutral score if ANTHROPIC_API_KEY is absent so the pipeline
    keeps running in dev / CI without secrets. The review UI surfaces the
    `error` field so a human knows the critic didn't run.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "score": 70,
            "flagged_spans": [],
            "rewrite_suggestion": "",
            "error": "ANTHROPIC_API_KEY not set — critic skipped",
        }

    try:
        from anthropic import Anthropic
    except ImportError:
        return {
            "score": 70,
            "flagged_spans": [],
            "rewrite_suggestion": "",
            "error": "anthropic SDK not installed — critic skipped",
        }

    client = Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=1024,
            system=critic_system_prompt(),
            messages=[{"role": "user", "content": text}],
        )
        raw = "".join(b.text for b in resp.content if hasattr(b, "text"))
        # Strip code fences if present.
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL)
        data = json.loads(raw)
        return {
            "score": int(data.get("score", 70)),
            "flagged_spans": data.get("flagged_spans") or [],
            "rewrite_suggestion": data.get("rewrite_suggestion") or "",
        }
    except Exception as exc:
        return {
            "score": 70,
            "flagged_spans": [],
            "rewrite_suggestion": "",
            "error": f"critic call failed: {exc}",
        }


# ── Combined report ───────────────────────────────────────────────────────────

def build_quality_report(
    variants: dict[str, dict],
    banned_phrases: list[str],
) -> dict[str, Any]:
    """Run all checks across every channel variant. Returns the report blob.

    `variants` is the shape stored on `ContentItem.variants_json`:
        {channel: {"body": str, "subject": str | None, "hashtags": [...], ...}}
    """
    per_channel: dict[str, dict] = {}
    overall_scores: list[int] = []

    for channel, variant in (variants or {}).items():
        body = (variant or {}).get("body") or ""
        critic = run_ai_tell_critic(body)
        per_channel[channel] = {
            "length":         check_length(body, channel),
            "em_dash_density": em_dash_density(body),
            "banned_found":   find_banned_phrases(body, banned_phrases),
            "ai_tell":        critic,
        }
        overall_scores.append(critic.get("score", 70))

    return {
        "per_channel":    per_channel,
        "ai_tell_score":  round(sum(overall_scores) / len(overall_scores), 1) if overall_scores else None,
        "any_banned":     any(c["banned_found"] for c in per_channel.values()),
        "any_oversize":   any(not c["length"]["ok"] for c in per_channel.values()),
    }
