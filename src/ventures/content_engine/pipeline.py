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
    # Clear any stale error_message from a prior failing run. Each later step
    # (caption fallback, image gen, video gen) overwrites this if it actually
    # fails — so a successful run no longer surfaces a stale error.
    item.error_message = None
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
        variants, text_failures = _generate_text_variants(item, brand, per_channel_briefs)

        item.variants_json = variants
        item.brief_json    = {"per_channel": per_channel_briefs, **slot}
        item.status        = "review_pending"  # will be re-set by quality_check
        if text_failures:
            # Surface per-channel fallback reasons so the operator stops seeing
            # silent `[DRAFT — auto-generation unavailable]` skeletons without
            # knowing why. Truncated to avoid blowing up the column.
            joined = "; ".join(text_failures)[:1500]
            item.error_message = f"caption-pack fallback: {joined}"
        db.commit()

        # Per-format media generation. Skipped cleanly when credentials are
        # absent — the human reviewer sees the gap in the review UI.
        if item.format in {"post", "carousel"}:
            try:
                _generate_static_visuals(item, brand, db)
            except Exception as exc:
                item.error_message = f"image generation skipped: {exc}"
                db.commit()
        elif item.format in {"reel", "short", "long_video"}:
            try:
                _generate_video_asset(item, brand, db)
            except Exception as exc:
                # Capture the stack so we can diagnose where exactly the
                # exception originated — without this we can't tell which
                # internal call slipped past the per-cue / per-tool catches.
                import traceback
                tb = traceback.format_exc()
                item.error_message = (
                    f"video generation skipped: {exc}\n\n"
                    f"--- traceback (top 1000 chars) ---\n{tb[-1000:]}"
                )
                db.commit()

        # Drive-upload health check. If the env var is missing every generated
        # asset stays on the worker's /tmp and the web service returns
        # "Asset not found" from /assets/{id}/file. Flag it once at the gate.
        import os as _os
        if not _os.environ.get("DRIVE_CONTENT_ENGINE_ID"):
            assets_no_drive = [a for a in (item.assets or []) if not a.drive_id and a.local_path]
            if assets_no_drive:
                prev = (item.error_message or "").strip()
                note = (
                    f"DRIVE_CONTENT_ENGINE_ID not set — {len(assets_no_drive)} asset(s) "
                    "are on the worker's local disk and not browsable from the web service."
                )
                item.error_message = (prev + "\n" + note).strip()[:1500]
                db.commit()

        return {"ok": True, "item_id": item_id, "variants_count": len(variants)}

    except Exception as exc:
        item.status = "failed"
        item.error_message = str(exc)[:1000]
        db.commit()
        return {"ok": False, "error": str(exc)}


def _generate_text_variants(
    item, brand, per_channel_briefs: dict[str, dict],
) -> tuple[dict[str, dict], list[str]]:
    """Call the existing platform skills to produce per-channel post bodies.

    Uses generate_caption_pack as the workhorse and synthesises the input
    transcript-shape from the brief. Falls back to a templated body if the
    skill can't run so the item still moves forward and the human reviewer
    sees the gap.

    Returns (variants_by_channel, failures) — `failures` is a list of human
    readable strings explaining why any channel fell back. Caller persists
    them on `item.error_message` so silent fallbacks are no longer hidden.
    """
    try:
        from aiplatform.skills.media.generate_caption_pack import generate_caption_pack
    except ImportError as exc:
        generate_caption_pack = None  # type: ignore[assignment]
        import_error = repr(exc)
    else:
        import_error = ""

    from ventures.content_engine.prompts import render_voice_block

    variants: dict[str, dict] = {}
    failures: list[str] = []
    voice_profile = brand.voice_profile_json or {}
    voice_block   = render_voice_block(voice_profile)

    for channel, brief in per_channel_briefs.items():
        platform_key = _channel_to_platform_key(channel)
        body = ""
        why = ""

        if generate_caption_pack is None:
            why = f"generate_caption_pack import failed: {import_error}"
        else:
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
                if not body:
                    # Surface BOTH the parser path that ran AND a snippet of
                    # the raw Claude response so we can diagnose without
                    # needing another deploy cycle.
                    parse_note = (result or {}).get("parse_note", "?")
                    raw = ((result or {}).get("raw") or "")[:600].replace("\n", " ⏎ ")
                    why = (
                        f"generate_caption_pack returned no caption for "
                        f"platform_key='{platform_key}' "
                        f"(parse_note={parse_note}, raw[:600]={raw!r})"
                    )
            except Exception as exc:
                body = ""
                why = f"generate_caption_pack raised {type(exc).__name__}: {str(exc)[:300]}"

        if not body:
            body = _fallback_body(brief, voice_profile)
            failures.append(f"{channel} -> {why or 'unknown'}")

        variants[channel] = {
            "body":     body,
            "subject":  None,
            "hashtags": [],
            "format":   brief.get("format"),
        }

    return variants, failures


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


# ── Drive upload for generated assets ────────────────────────────────────────
#
# Worker and web run in separate containers; their `/tmp` filesystems are not
# shared. If we only record `local_path`, the web service returns 404 from
# `/assets/{id}/file` because the file lives on a different host. Solve it the
# same way podcast audio did: upload to Drive in the worker, store `drive_id`
# + a publicly fetchable `url` on the asset row so the file endpoint can
# 302-redirect to it.

def _upload_asset_to_drive(asset, item, brand, db, filename_hint: str = "") -> None:
    """Upload the asset's local file to the content-engine Drive folder.

    Best-effort: any failure leaves `local_path` intact and logs to
    `item.error_message`. The asset row is committed either way so the
    download endpoint can still try `local_path` (which works only for
    web-served items, but is fine when worker = web in dev).
    """
    import os
    from pathlib import Path

    folder_id = os.environ.get("DRIVE_CONTENT_ENGINE_ID")
    if not folder_id:
        return  # No drive folder configured — leave local_path; surfaced once at gate.
    if not asset.local_path:
        return
    if not Path(asset.local_path).exists():
        return

    try:
        from aiplatform.skills.storage.drive_write import drive_write
    except ImportError:
        return

    # Compose a readable filename: <brand>__<format>__<role>__<itemid8>.<ext>
    src = Path(asset.local_path)
    ext = src.suffix or ""
    role = (asset.role or asset.kind or "asset").replace("/", "_")
    parts = [
        (brand.name or "brand").replace(" ", "_")[:40],
        (item.format or "item"),
        role,
        str(item.id)[:8],
    ]
    if filename_hint:
        parts.insert(2, filename_hint[:40])
    filename = "__".join(parts) + ext

    try:
        result = drive_write(
            local_path=str(src),
            folder_id=folder_id,
            filename=filename,
            share_anyone_with_link=True,
        )
    except Exception as exc:
        # Non-fatal — keep local_path, surface so the operator knows why
        # "Open" still shows Asset not found from a different container.
        prev = (item.error_message or "").strip()
        note = f"drive upload failed for asset {asset.id} ({asset.role}): {exc}"
        item.error_message = (prev + "\n" + note).strip()[:1500]
        db.commit()
        return

    file_id = result["file_id"]
    asset.drive_id = file_id
    # Use the direct-download URL so the IG/FB Graph API can fetch the binary
    # AND the operator's `/assets/{id}/file` endpoint can 302-redirect for an
    # inline preview. Drive serves files <100 MB without an interstitial.
    asset.url = f"https://drive.google.com/uc?export=download&id={file_id}"
    meta = dict(asset.meta_json or {})
    meta["drive_web_view_link"] = result.get("web_view_link", "")
    meta["drive_filename"] = result.get("filename", filename)
    asset.meta_json = meta
    db.commit()


def _generate_static_visuals(item, brand, db) -> None:
    """Generate a primary image (and slide images for carousel).

    For carousels we plan all slides up-front via `carousel_brief.plan_carousel_slides`
    so the set carries a single style anchor across every slide. For single-image
    posts we run a one-shot prompt. Best-effort throughout — per-image failure
    won't abort the rest.
    """
    try:
        from aiplatform.skills.media.generate_image import generate_image
    except ImportError:
        return

    from aiplatform.database.models import ContentAsset

    topic = item.topic or (item.brief_json or {}).get("topic") or brand.name
    brief = item.brief_json or {}

    if item.format == "carousel":
        from aiplatform.skills.media.carousel_brief import plan_carousel_slides
        slides = plan_carousel_slides(
            topic=topic,
            pillar=brief.get("pillar") or item.pillar,
            angle=brief.get("angle"),
            audience=(brief.get("audience") or {}).get("description"),
            voice_profile=brand.voice_profile_json or {},
            slide_count=5,
            aspect_ratio="1:1",
        )
        for slide in slides:
            try:
                result = generate_image(prompt=slide["prompt"],
                                         aspect_ratio="1:1",
                                         quality_tier="standard")
                role = "primary" if slide["slide_index"] == 1 \
                        else f"carousel_slide_{slide['slide_index']}"
                asset = ContentAsset(
                    item_id=item.id, kind="image", role=role, channel=None,
                    local_path=result.get("image_path"),
                    meta_json={
                        "width":         result.get("width"),
                        "height":        result.get("height"),
                        "tool_used":     result.get("tool_used"),
                        "slide_index":   slide["slide_index"],
                        "slide_role":    slide["role"],
                        "slide_caption": slide["caption"],
                    },
                    cost_usd=result.get("cost"),
                )
                db.add(asset)
                db.flush()  # populate asset.id before Drive upload
                _upload_asset_to_drive(
                    asset, item, brand, db,
                    filename_hint=f"slide{slide['slide_index']}",
                )
            except Exception:
                continue
        db.commit()
        return

    # Single-image post.
    prompt = (
        f"Editorial illustration for an accessibility article. Topic: {topic}. "
        "Realistic, modern, no text overlays, neutral background."
    )
    try:
        result = generate_image(prompt=prompt, aspect_ratio="1:1", quality_tier="standard")
        if result.get("failover_from"):
            item.error_message = (
                f"image generation fell over from {result['failover_from']} to "
                f"{result.get('tool_used')} — {result.get('failover_reason', '')[:200]}"
            )
        asset = ContentAsset(
            item_id=item.id, kind="image", role="primary", channel=None,
            local_path=result.get("image_path"),
            meta_json={
                "width":           result.get("width"),
                "height":          result.get("height"),
                "tool_used":       result.get("tool_used"),
                "failover_from":   result.get("failover_from"),
                "failover_reason": result.get("failover_reason"),
            },
            cost_usd=result.get("cost"),
        )
        db.add(asset)
        db.flush()  # populate asset.id before Drive upload
        _upload_asset_to_drive(asset, item, brand, db)
        db.commit()
    except Exception:
        return


# ── Quality check ────────────────────────────────────────────────────────────

def run_quality_check(item_id: str, db) -> dict[str, Any]:
    """Run the AI-tell critic + length/banned checks. Sets the item's next status.

    If the brand's `auto_approve_min_score` is set, the AI-tell score meets it,
    and no banned phrases / oversize variants triggered, the item moves
    straight to `approved` — skipping the human review gate. Otherwise it
    lands at `review_pending`.
    """
    from datetime import datetime, timezone
    from aiplatform.database.models import ContentItem, ContentBrand
    from ventures.content_engine.quality_gate import build_quality_report

    item = db.get(ContentItem, uuid.UUID(item_id))
    if not item:
        return {"ok": False, "error": "item not found"}

    brand = db.get(ContentBrand, item.brand_id)
    banned = (brand.banned_phrases if brand else None) or []
    threshold = int(getattr(brand, "auto_approve_min_score", 0) or 0)

    report = build_quality_report(item.variants_json or {}, banned)
    item.quality_report_json = report

    ai_score = report.get("ai_tell_score")
    can_auto_approve = (
        threshold > 0
        and ai_score is not None
        and ai_score >= threshold
        and not report.get("any_banned")
        and not report.get("any_oversize")
    )
    if can_auto_approve:
        item.status = "approved"
        item.approved_at = datetime.now(timezone.utc)
        item.review_notes = (
            f"Auto-approved: AI-tell {ai_score} ≥ threshold {threshold}, "
            "no banned phrases, all variants within length budget."
        )
    else:
        item.status = "review_pending"

    db.commit()
    return {"ok": True, "item_id": item_id, "ai_tell_score": ai_score,
            "auto_approved": can_auto_approve}


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
        from aiplatform.skills.comms.publishers.oauth import ensure_fresh_token
    except ImportError as exc:
        item.status = "failed"
        item.error_message = f"publishers registry not importable: {exc}"
        db.commit()
        return {"ok": False, "error": str(exc)}

    results: list[dict] = []
    media_paths, media_urls = _asset_paths_for(item, db)

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

        # Refresh near-expiry tokens (currently only YouTube has refresh wired).
        access_token = ensure_fresh_token(account, db=db) if account else None

        # IG needs public URLs; for local-only assets, expose them via the
        # content-engine public asset endpoint.
        per_channel_urls = list(media_urls)
        if channel == "instagram_business" and not per_channel_urls:
            per_channel_urls = _public_urls_for(item, db)

        req = PublishRequest(
            body=variant.get("body") or "",
            title=variant.get("subject") or item.title or "",
            hashtags=variant.get("hashtags") or [],
            media_paths=media_paths,
            media_urls=per_channel_urls,
            channel=channel,
            scheduled_for_iso=(item.scheduled_for.isoformat() if item.scheduled_for else ""),
        )
        config = {
            "access_token":   access_token,
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


def _asset_paths_for(item, db) -> tuple[list[str], list[str]]:
    """Split this item's assets into (local file paths, public URLs).

    Carousel slides are ordered by asset id, so the primary image is first.
    Publishers receive both lists and pick whichever each platform supports.
    """
    paths: list[str] = []
    urls:  list[str] = []
    for asset in sorted((item.assets or []), key=lambda a: a.id):
        if asset.url:
            urls.append(asset.url)
        elif asset.local_path:
            paths.append(asset.local_path)
    return paths, urls


def _public_urls_for(item, db) -> list[str]:
    """Build public content-engine URLs for any local-only assets.

    IG and (sometimes) FB need a URL the Graph API can fetch from. The
    `/api/ventures/content-engine/assets/{id}/file` endpoint is public
    (asset id is a non-listed integer) and serves local files directly.
    """
    import os
    base = os.environ.get("OAUTH_REDIRECT_BASE_URL", "https://api.planbadmin.com").rstrip("/")
    out: list[str] = []
    for asset in sorted((item.assets or []), key=lambda a: a.id):
        if asset.url:
            out.append(asset.url)
        elif asset.local_path:
            out.append(f"{base}/api/ventures/content-engine/assets/{asset.id}/file")
    return out


# ── Video asset generation ───────────────────────────────────────────────────

# Approx character counts per format — drives narration length.
_VIDEO_SCRIPT_BUDGET = {
    "reel":       (350,  700),   # 25–45 s narration
    "short":      (350,  700),
    "long_video": (2000, 4500),  # 3–7 min narration
}

# Aspect ratio per format.
_VIDEO_ASPECT = {
    "reel":       "9:16",
    "short":      "9:16",
    "long_video": "16:9",
}


def _generate_video_asset(item, brand, db) -> None:
    """Generate a scripted explainer video for reel / short / long_video items.

    Uses Claude to write a narration script grounded in the item's brief,
    pre-selects 4-6 visual cues (mix of generated Imagen stills + Pexels
    stock for variety), then calls `generate_video_explainer` to assemble.

    Best-effort: any failure falls through to the human reviewer with a
    flagged error rather than crashing the whole generation pass.
    """
    from aiplatform.database.models import ContentAsset

    try:
        from aiplatform.skills.media.generate_video_explainer import generate_video_explainer
    except ImportError:
        return

    aspect = _VIDEO_ASPECT.get(item.format, "9:16")
    brief = item.brief_json or {}
    pillar = brief.get("pillar") or item.pillar or ""
    topic  = brief.get("topic")  or item.topic  or brand.name

    char_budget = _VIDEO_SCRIPT_BUDGET.get(item.format, (350, 700))
    script, visuals, draft_reason = _draft_video_script_and_visuals(
        brand=brand,
        brief=brief,
        char_budget=char_budget,
    )
    if not script:
        item.error_message = (
            f"video skipped: script generation returned no usable script "
            f"(format={item.format}, char_budget={char_budget}, reason={draft_reason})"
        )
        db.commit()
        return

    # Hard safety net: even though `generate_video_explainer` wraps each cue
    # and `generate_image` auto-falls-back on quota errors, there are paths
    # (TTS provider 5xx, unexpected Gemini SDK exceptions, etc) that could
    # still surface as a raised exception. Catch them here so the item gets
    # `error_message` set but never crashes through to the outer except — the
    # text variants are already saved and the item still lands at
    # `review_pending` for the operator to ship as a text/image post or
    # regenerate later.
    try:
        result = generate_video_explainer(
            script=script,
            visuals=visuals,
            aspect_ratio=aspect,
            caption_style="word_pop",
        )
    except Exception as exc:
        import traceback
        from aiplatform.skills.media.generate_image import _is_quota_error
        kind = "quota/capacity error" if _is_quota_error(exc) else "internal error"
        item.error_message = (
            f"video assembly raised ({kind}): {exc}\n\n"
            f"--- traceback (top 800 chars) ---\n{traceback.format_exc()[-800:]}"
        )
        db.commit()
        return

    if not result.get("video_path"):
        item.error_message = f"video assembly failed: {result.get('error', 'unknown')}"
        db.commit()
        return

    # If any per-slide failover happened, surface it as a non-fatal warning
    # so the human reviewer sees that one or more cues came from stock instead
    # of the requested generator (Imagen / DALL-E).
    visual_failures = result.get("visual_failures") or []
    if visual_failures:
        summary = "; ".join(
            f"slide {f.get('index')}: {f.get('note', '')[:120]}"
            for f in visual_failures[:5]
        )
        item.error_message = f"video produced with {len(visual_failures)} cue fallback(s) — {summary}"

    asset = ContentAsset(
        item_id=item.id,
        kind="video",
        role="primary",
        channel=None,
        local_path=result["video_path"],
        meta_json={
            "aspect_ratio":    result.get("aspect_ratio"),
            "duration_s":      result.get("duration_s"),
            "components":      result.get("components"),
            "visual_failures": visual_failures,
            "topic":           topic,
            "pillar":          pillar,
        },
        cost_usd=result.get("cost_usd"),
    )
    db.add(asset)
    db.flush()  # populate asset.id before Drive upload
    _upload_asset_to_drive(asset, item, brand, db)
    db.commit()


def _draft_video_script_and_visuals(
    *, brand, brief: dict, char_budget: tuple[int, int],
) -> tuple[str, list[dict], str]:
    """Ask Claude to draft a script + visual cues. Degrades cleanly when no key.

    Returns (script, [visuals], reason) where each visual is a dict the
    generate_video_explainer skill accepts. `reason` describes why we returned
    an empty/fallback script — surfaced via `item.error_message` so the operator
    knows whether to regenerate or ship without video.
    """
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    topic = brief.get("topic") or brief.get("pillar") or brand.name

    # Deterministic fallback — used when no LLM key is available so the human
    # reviewer can still see a draft to edit.
    if not api_key:
        script = (
            f"{topic}. {brief.get('angle') or ''}. "
            "Here's the single thing to remember. "
            "Open with the example, then the rule. "
            "Action you can take today: audit one component, one criterion."
        )
        return script, _default_visuals(brand, brief), "no_api_key_fallback"

    try:
        from anthropic import Anthropic
    except ImportError:
        return "", _default_visuals(brand, brief), "anthropic_sdk_missing"

    from ventures.content_engine.prompts import render_voice_block
    voice_block = render_voice_block(brand.voice_profile_json or {})

    user_prompt = (
        f"{voice_block}\n\n"
        f"Draft a short scripted explainer video for {brand.name}.\n"
        f"Topic: {topic}\n"
        f"Pillar: {brief.get('pillar', '')}\n"
        f"Angle: {brief.get('angle', '')}\n"
        f"Audience: {(brief.get('audience') or {}).get('description', '')}\n"
        f"Channel CTA: {brief.get('cta', '')}\n"
        f"Sources to ground specifics:\n"
        + "\n".join(f"  - {s.get('url', '')}: {s.get('relevance', '')}"
                    for s in (brief.get('sources') or [])[:3])
        + "\n\nReturn JSON with this exact shape (no prose, no code fences):\n"
        + '{\n'
        + '  "script": "...full narration text, '
        + f'{char_budget[0]}-{char_budget[1]} chars...",\n'
        + '  "visuals": [\n'
        + '    {"kind": "stock_query"|"generated", "value": "search query or image prompt", "caption": "this scene\'s captioned phrase"},\n'
        + '    ... 4-6 entries total ...\n'
        + '  ]\n'
        + '}\n'
        "Use kind=stock_query for relatable b-roll (people, scenes); "
        "kind=generated for concept diagrams or specific UI examples; "
        "value for stock_query is a 2-4 word Pexels query."
    )

    # Scale max_tokens with char_budget so the JSON envelope (script +
    # 4–6 visual cues + keys) doesn't truncate mid-string. Rough budget:
    # ~1 token / 3 chars script + ~600 chars of cue metadata.
    max_tokens = min(8192, max(2048, (char_budget[1] // 3) + 1500))

    raw = ""
    try:
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": user_prompt}],
        )
        import json, re
        raw = "".join(b.text for b in resp.content if hasattr(b, "text")).strip()
        stop_reason = getattr(resp, "stop_reason", None)
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL)
        data = json.loads(raw)
        script = (data.get("script") or "").strip()
        visuals = [v for v in (data.get("visuals") or []) if v.get("value")]
        if script and visuals:
            return script, visuals, "ok"
        return "", _default_visuals(brand, brief), (
            f"empty_payload (stop_reason={stop_reason}, script_len={len(script)}, "
            f"visuals_len={len(visuals)})"
        )
    except Exception as exc:
        return "", _default_visuals(brand, brief), (
            f"{type(exc).__name__}: {str(exc)[:200]} | "
            f"raw_head={raw[:200]!r}"
        )


def _default_visuals(brand, brief: dict) -> list[dict]:
    topic = brief.get("topic") or brand.name
    return [
        {"kind": "stock_query", "value": "accessibility laptop",
         "caption": f"{topic} — here's the issue."},
        {"kind": "stock_query", "value": "person screen reader",
         "caption": "Real users feel this every day."},
        {"kind": "generated", "value":
            f"Editorial diagram illustrating {topic}, clean modern style, "
            "no text overlay, accessible colour palette.",
         "caption": "The pattern that fixes it."},
        {"kind": "stock_query", "value": "designer office",
         "caption": "Audit one component this week."},
    ]
