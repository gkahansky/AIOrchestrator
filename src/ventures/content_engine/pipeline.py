"""Content Engine pipeline — Celery task entrypoints.

Three thin orchestration functions composed from venture-agnostic skills:
  - run_item_generation(item_id) — generates per-channel variants for one item.
  - run_quality_check(item_id)   — runs AI-tell critic + length/banned checks.
  - run_publish_item(item_id)    — dispatches to channel publishers.

All three update the `ContentItem` row in place and never block on side
effects (Drive uploads degrade to local paths, missing API keys degrade
to assisted-send). The router and worker call these functions; the
business logic lives here so the worker stays thin.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid


# ── Item generation ──────────────────────────────────────────────────────────

def run_item_generation(item_id: str, db) -> dict[str, Any]:
    """Generate per-channel variants for one ContentItem.

    Uses the existing media skills:
      - generate_caption_pack for the per-channel post text
      - generate_blog_post when format == 'blog'
      - generate_newsletter_draft when format == 'newsletter'
      - generate_image for static images (carousel = N calls)

    Image / video skills are tier-gated and skip cleanly if API keys are
    absent — the item still gets text variants and lands in review_pending
    so a human can decide how to handle the gap.
    """
    from aiplatform.database.models import ContentItem, ContentBrand, ContentAsset
    from ventures.content_engine.briefs import build_brief

    item = db.get(ContentItem, uuid.UUID(item_id))
    if not item:
        return {"ok": False, "error": "item not found"}

    brand = db.get(ContentBrand, item.brand_id)
    if not brand:
        return {"ok": False, "error": "brand not found"}

    item.status = "generating"
    db.commit()

    try:
        slot = item.brief_json or {
            "index":   None,
            "channel": (item.channels or ["linkedin_page"])[0],
            "format":  item.format,
            "pillar":  item.pillar,
            "topic":   item.topic,
        }
        brand_dict = {
            "name":             brand.name,
            "description":      brand.description,
            "target_personas":  brand.target_personas or [],
            "theme_weights":    brand.theme_weights or {},
            "voice_profile_json": brand.voice_profile_json or {},
        }

        # Refresh the brief with live sources for every requested channel.
        per_channel_briefs: dict[str, dict] = {}
        for channel in (item.channels or []):
            slot_for_channel = {**slot, "channel": channel}
            per_channel_briefs[channel] = build_brief(slot_for_channel, brand_dict)

        # Generate per-channel text via the existing caption-pack skill where
        # supported, with a brand-voice block prepended into context.
        variants = _generate_text_variants(item, brand, per_channel_briefs)

        item.variants_json = variants
        item.brief_json    = {"per_channel": per_channel_briefs, **slot}
        item.status        = "review_pending"  # will be re-set by quality_check
        db.commit()

        # Cheap static image for post / carousel formats — skipped cleanly
        # if no image-gen credentials are available.
        if item.format in {"post", "carousel"}:
            try:
                _generate_static_visuals(item, brand, db)
            except Exception as exc:
                item.error_message = f"image generation skipped: {exc}"
                db.commit()

        return {"ok": True, "item_id": item_id, "variants_count": len(variants)}

    except Exception as exc:
        item.status = "failed"
        item.error_message = str(exc)[:1000]
        db.commit()
        return {"ok": False, "error": str(exc)}


def _generate_text_variants(item, brand, per_channel_briefs: dict[str, dict]) -> dict[str, dict]:
    """Call the existing platform skills to produce per-channel post bodies.

    Uses generate_caption_pack as the workhorse and synthesises the input
    transcript-shape from the brief. Falls back to a templated body if the
    skill can't run (no API key / import failure) so the item still moves
    forward and the human reviewer sees the gap.
    """
    try:
        from aiplatform.skills.media.generate_caption_pack import generate_caption_pack
    except ImportError:
        generate_caption_pack = None  # type: ignore[assignment]

    from ventures.content_engine.prompts import render_voice_block

    variants: dict[str, dict] = {}
    voice_profile = brand.voice_profile_json or {}
    voice_block   = render_voice_block(voice_profile)

    for channel, brief in per_channel_briefs.items():
        platform_key = _channel_to_platform_key(channel)
        body = ""

        if generate_caption_pack is not None:
            try:
                context = {
                    "show_name": brand.name,
                    "title":     brief.get("topic", ""),
                    "niche":     brief.get("pillar", ""),
                    "audience":  (brief.get("audience") or {}).get("description", ""),
                    "show_notes": brief.get("angle", ""),
                }
                result = generate_caption_pack(
                    transcript=_brief_as_pseudo_transcript(brief),
                    context=context,
                    platforms=[platform_key],
                    captions_per_platform=1,
                    brand_voice_injection=voice_block,
                )
                captions = (result or {}).get("captions", {}).get(platform_key, [])
                body = captions[0] if captions else ""
            except Exception:
                body = ""

        if not body:
            body = _fallback_body(brief, voice_profile)

        variants[channel] = {
            "body":     body,
            "subject":  None,
            "hashtags": [],
            "format":   brief.get("format"),
        }

    return variants


def _channel_to_platform_key(channel: str) -> str:
    """Map our channel slugs to the platform keys generate_caption_pack expects."""
    return {
        "linkedin_page":      "linkedin",
        "facebook_page":      "facebook",
        "instagram_business": "instagram",
        "youtube_channel":    "youtube",
    }.get(channel, "linkedin")


def _brief_as_pseudo_transcript(brief: dict) -> str:
    """Caption-pack expects a transcript-ish text input — give it the brief shape."""
    parts = [
        f"Topic: {brief.get('topic', '')}",
        f"Pillar: {brief.get('pillar', '')}",
        f"Angle: {brief.get('angle', '')}",
        f"Hook: {brief.get('hook', '')}",
        f"CTA: {brief.get('cta', '')}",
    ]
    for s in (brief.get("sources") or [])[:3]:
        parts.append(f"Source: {s.get('url', '')} — {s.get('relevance', '')}")
    return "\n".join(p for p in parts if p.strip().split(":", 1)[-1].strip())


def _fallback_body(brief: dict, voice_profile: dict) -> str:
    """Deterministic placeholder body when generation can't run.

    Lets the human reviewer see something concrete to edit instead of a blank
    field. Marked with a leading [DRAFT] tag the review UI can flag.
    """
    topic = brief.get("topic") or brief.get("pillar") or "Accessibility"
    hook  = brief.get("hook") or f"Quick note on {topic.lower()}."
    cta   = brief.get("cta") or ""
    return f"[DRAFT — auto-generation unavailable]\n\n{hook}\n\n{cta}".strip()


def _generate_static_visuals(item, brand, db) -> None:
    """Generate a primary image (and slide images for carousel). Best-effort."""
    try:
        from aiplatform.skills.media.generate_image import generate_image
    except ImportError:
        return

    from aiplatform.database.models import ContentAsset

    n_images = 5 if item.format == "carousel" else 1
    topic = item.topic or (item.brief_json or {}).get("topic") or brand.name

    for i in range(n_images):
        try:
            prompt = (
                f"Editorial illustration for an accessibility article. Topic: {topic}. "
                "Realistic, modern, no text overlays, neutral background. "
                f"Slide {i + 1} of {n_images}." if n_images > 1 else
                f"Editorial illustration for an accessibility article. Topic: {topic}. "
                "Realistic, modern, no text overlays, neutral background."
            )
            result = generate_image(prompt=prompt, aspect_ratio="1:1", quality_tier="standard")
            asset = ContentAsset(
                item_id=item.id,
                kind="image",
                role="primary" if i == 0 else f"carousel_slide_{i + 1}",
                channel=None,
                local_path=result.get("image_path"),
                meta_json={
                    "width":     result.get("width"),
                    "height":    result.get("height"),
                    "tool_used": result.get("tool_used"),
                },
                cost_usd=result.get("cost"),
            )
            db.add(asset)
        except Exception:
            # Per-image failure shouldn't abort the rest.
            continue

    db.commit()


# ── Quality check ────────────────────────────────────────────────────────────

def run_quality_check(item_id: str, db) -> dict[str, Any]:
    """Run the AI-tell critic + length/banned checks. Sets status to review_pending."""
    from aiplatform.database.models import ContentItem, ContentBrand
    from ventures.content_engine.quality_gate import build_quality_report

    item = db.get(ContentItem, uuid.UUID(item_id))
    if not item:
        return {"ok": False, "error": "item not found"}

    brand = db.get(ContentBrand, item.brand_id)
    banned = (brand.banned_phrases if brand else None) or []

    report = build_quality_report(item.variants_json or {}, banned)
    item.quality_report_json = report
    item.status = "review_pending"
    db.commit()

    return {"ok": True, "item_id": item_id, "ai_tell_score": report.get("ai_tell_score")}


# ── Publish dispatch ─────────────────────────────────────────────────────────

def run_publish_item(item_id: str, db) -> dict[str, Any]:
    """Publish an approved item to each requested channel.

    For each channel:
      - look up SocialAccount(brand_id=item.brand_id, platform=channel)
      - resolve a publisher from the registry
      - call publisher.publish(req, config)
      - persist a PublishJob row

    On any per-channel failure we mark THAT publish_job failed but keep
    going — one bad channel shouldn't block the others.
    """
    from aiplatform.database.models import ContentItem, SocialAccount, PublishJob

    item = db.get(ContentItem, uuid.UUID(item_id))
    if not item:
        return {"ok": False, "error": "item not found"}

    if item.status not in {"approved", "scheduled"}:
        return {"ok": False, "error": f"item status is '{item.status}', cannot publish"}

    item.status = "publishing"
    db.commit()

    try:
        from aiplatform.skills.comms.publishers import HANDLERS as PUBLISHERS
        from aiplatform.skills.comms.publishers.base import PublishRequest
    except ImportError as exc:
        item.status = "failed"
        item.error_message = f"publishers registry not importable: {exc}"
        db.commit()
        return {"ok": False, "error": str(exc)}

    results: list[dict] = []

    for channel in (item.channels or []):
        variant = (item.variants_json or {}).get(channel, {})
        account = db.query(SocialAccount).filter(
            SocialAccount.brand_id == item.brand_id,
            SocialAccount.platform == channel,
            SocialAccount.enabled.is_(True),
        ).first()

        handler = PUBLISHERS.get(channel)
        if handler is None:
            pj = PublishJob(
                item_id=item.id, channel=channel, status="failed",
                error_message=f"no publisher registered for {channel}",
            )
            db.add(pj)
            results.append({"channel": channel, "status": "failed"})
            continue

        req = PublishRequest(
            body=variant.get("body") or "",
            title=variant.get("subject") or item.title or "",
            hashtags=variant.get("hashtags") or [],
            media_paths=_asset_paths_for(item, channel),
            channel=channel,
        )
        config = {
            "access_token":   getattr(account, "access_token", None),
            "account_id":     getattr(account, "account_id", None),
            "account_name":   getattr(account, "account_name", None),
            "meta":           getattr(account, "meta_json", None) or {},
        }

        try:
            result = handler.publish(req, config)
            pj = PublishJob(
                item_id=item.id,
                channel=channel,
                status=result.status,
                external_post_id=result.external_post_id or None,
                external_url=result.external_url or None,
                deep_link=result.deep_link or None,
                error_message=result.error or None,
                response_json=result.response or {},
            )
            db.add(pj)
            results.append({"channel": channel, "status": result.status})
        except Exception as exc:
            pj = PublishJob(
                item_id=item.id, channel=channel, status="failed",
                error_message=str(exc)[:1000],
            )
            db.add(pj)
            results.append({"channel": channel, "status": "failed"})

    # Aggregate item-level status — published if any channel succeeded;
    # otherwise failed.
    any_ok = any(r["status"] in {"success", "awaiting_manual"} for r in results)
    item.status = "published" if any_ok else "failed"
    if any_ok:
        item.published_at = datetime.now(timezone.utc)
    db.commit()

    return {"ok": any_ok, "item_id": item_id, "results": results}


def _asset_paths_for(item, channel: str) -> list[str]:
    """Pick the media file paths to attach for a given channel.

    For now: primary image first, then carousel slides in order, ignoring
    channel-specific overrides (which can come in a later phase).
    """
    paths: list[str] = []
    for asset in sorted((item.assets or []), key=lambda a: a.id):
        if asset.local_path or asset.url:
            paths.append(asset.local_path or asset.url)
    return paths
