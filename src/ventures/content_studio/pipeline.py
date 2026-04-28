"""
Content Studio pipeline — Service A (Podcast Show Notes) + Service B (Content Repurposing Pack).

Service A phases (service_type = "show_notes"):
    1 — Transcription           (OpenAI Whisper)
    2 — Content Generation      (Claude API, tier-aware show notes / social / SEO)
    3 — Packaging               (Google Doc creation)
    3b — Add-ons (optional)     (brand voice, promo copy, social calendar, ...)
    4 — Human Review ★          (email notification + approval gate)
    5 — Delivery

Service B phases (service_type = "repurposing_pack"):
    1 — Input Processing        (video → FFmpeg audio extraction if needed, then Whisper)
    2 — Core Generation         (show notes + timestamps via Claude)
    2b — Extended Outputs       (blog post, per-platform captions, newsletter via skills)
    3 — Packaging               (Google Doc creation)
    4 — Human Review ★★         (ALWAYS on — never auto-approved)
    5 — Delivery

Order status state machine:
    pending → transcribing → transcribed → generating → generated →
    packaging → packaged → review_pending → approved →
    delivering → delivered
              └→ addons_pending → [addon pipeline] → addons_complete → packaged
              └→ revision_requested → re_delivering → delivered
              └→ failed
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import anthropic

try:
    import redis as redis_lib
    _redis_available = True
except ImportError:
    _redis_available = False

logger = logging.getLogger(__name__)

def _get_redis() -> "redis_lib.Redis | None":
    """Return a Redis client if REDIS_URL is set and redis package is available."""
    if not _redis_available:
        return None
    url = os.getenv("REDIS_URL")
    if not url:
        return None
    try:
        return redis_lib.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
    except Exception:
        return None

_BRAND_VOICE_TTL = 60 * 60 * 24 * 90  # 90 days

from aiplatform.skills.media.transcribe_audio import transcribe_audio
from aiplatform.skills.media.generate_brand_voice import generate_brand_voice
from aiplatform.skills.media.generate_promo_copy import generate_promo_copy
from aiplatform.skills.media.generate_blog_post import generate_blog_post
from aiplatform.skills.media.generate_caption_pack import generate_caption_pack
from aiplatform.skills.media.generate_newsletter_draft import generate_newsletter_draft
from aiplatform.skills.media.generate_social_calendar import generate_social_calendar
from aiplatform.skills.media.generate_email_sequence import generate_email_sequence
from aiplatform.skills.media.generate_guest_outreach import generate_guest_outreach
from aiplatform.skills.media.generate_launch_playbook import generate_launch_playbook
from aiplatform.skills.research.audit_landing_page import audit_landing_page, FetchError, PageTooLarge
from aiplatform.skills.research.generate_competitive_analysis import generate_competitive_analysis
from aiplatform.skills.storage.create_gdoc import create_gdoc
from aiplatform.skills.storage.drive_organise import create_folder
from aiplatform.skills.storage.drive_write import drive_write
from aiplatform.skills.comms.send_email import send_email
from aiplatform.skills.finance.log_cost import log_cost
from aiplatform.skills.finance.log_revenue import log_revenue
from ventures.content_studio import config
from ventures.content_studio.content_pdf import generate_full_pdf, generate_sample_pdf
from ventures.content_studio.prompts import (
    SYSTEM_PROMPT,
    REPURPOSING_SYSTEM_PROMPT,
    build_content_prompt,
    build_repurposing_prompt,
    parse_content_response,
    parse_repurposing_response,
)

_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}


def run_order(order: dict, output_dir: str | None = None) -> dict:
    """
    Run all pipeline phases for a single order.
    Saves order state after each phase — safe to re-run from any checkpoint.

    Returns the updated order dict.
    """
    if output_dir is None:
        output_dir = str(Path(config.OUTPUT_DIR) / "content_studio")
    work_dir = Path(output_dir) / order["order_id"]
    work_dir.mkdir(parents=True, exist_ok=True)
    _save_order(order, work_dir)

    try:
        # ── Phase 1: Transcription ─────────────────────────────────────────────
        if order["status"] in ("pending", "transcribing"):
            order["status"] = "transcribing"
            _save_order(order, work_dir)
            transcript_data = _run_phase1_transcribe(order, work_dir)
            order["status"] = "transcribed"
            order["transcript_data"] = transcript_data
            _save_order(order, work_dir)
        else:
            transcript_data = order.get("transcript_data") or _load_json(work_dir / "transcript_data.json")

        # ── Phase 2: Content Generation ────────────────────────────────────────
        if order["status"] in ("transcribed", "generating"):
            order["status"] = "generating"
            _save_order(order, work_dir)
            content = _run_phase2_generate(order, transcript_data, work_dir)
            order["status"] = "generated"
            order["content"] = content
            _save_order(order, work_dir)
        else:
            content = order.get("content") or _load_json(work_dir / "content.json")

        # ── Phase 2b: Extended Outputs (Service B only) ────────────────────────
        if (
            order.get("service_type") == "repurposing_pack"
            and order["status"] in ("generated", "generating_extended")
        ):
            order["status"] = "generating_extended"
            _save_order(order, work_dir)
            content = _run_phase2b_repurposing_extended(order, content, work_dir)
            order["status"] = "generated"
            order["content"] = content
            _save_order(order, work_dir)

        # ── Phase 3: Packaging ─────────────────────────────────────────────────
        if order["status"] in ("generated", "packaging"):
            order["status"] = "packaging"
            _save_order(order, work_dir)
            gdoc = _run_phase3_package(order, content, work_dir)
            order["status"] = "packaged"
            order["gdoc"] = gdoc
            _save_order(order, work_dir)
        else:
            gdoc = order.get("gdoc")

        # ── Phase 3b: Add-ons (optional) ──────────────────────────────────────
        add_ons = order.get("add_ons") or []
        if add_ons and order["status"] in ("packaged", "addons_pending"):
            order["status"] = "addons_pending"
            _save_order(order, work_dir)
            addon_results = _run_addons(order, content, work_dir)
            order["addon_results"] = addon_results
            order["status"] = "packaged"   # return to packaged so review gate proceeds
            _save_order(order, work_dir)

        # ── Phase 4: Human Review ──────────────────────────────────────────────
        if order["status"] in ("packaged", "review_pending"):
            order["status"] = "review_pending"
            _save_order(order, work_dir)
            _run_phase4_review(order, gdoc)
            # Service B review is ALWAYS required — it is the product's differentiator.
            # Service A auto-approve is controlled by config + per-order flag.
            service_b = order.get("service_type") == "repurposing_pack"
            can_auto_approve = (
                not service_b
                and not config.REPURPOSING_PACK_HUMAN_REVIEW_ALWAYS
                and (config.AUTO_APPROVE or order.get("auto_approve"))
            )
            if can_auto_approve:
                order["status"] = "approved"
                _save_order(order, work_dir)
            else:
                print(f"\nPipeline paused at review gate.")
                print(f"Set order status to 'approved' in {work_dir / 'order.json'} to continue.\n")
                return order
        elif order["status"] == "approved":
            # Re-dispatched from API after human approval — reload gdoc from order
            gdoc = order.get("gdoc") or gdoc

        # ── Phase 5: Delivery ──────────────────────────────────────────────────
        if order["status"] == "approved":
            order["status"] = "delivering"
            _save_order(order, work_dir)
            _run_phase5_deliver(order, gdoc)
            order["status"] = "delivered"
            order["delivered_at"] = datetime.utcnow().isoformat()
            _save_order(order, work_dir)
            # Only log revenue for paid orders — skip free samples
            tier_info = config.TIERS.get(order.get("tier", "starter"), {})
            if order.get("client_email"):
                # Bundle price overrides tier price when a bundle SKU was applied
                bundle_sku = order.get("bundle_sku", "")
                bundle_info = config.BUNDLES.get(bundle_sku, {})
                amount_usd = bundle_info.get("price_usd") or tier_info.get("price_usd", 0)
                description = (
                    f"{bundle_info.get('name', bundle_sku)} — {order.get('show_name','')[:60]}"
                    if bundle_sku
                    else f"{order.get('tier','starter')} — {order.get('show_name','')[:80]}"
                )
                log_revenue(
                    venture="content_studio",
                    source=order.get("source", "direct"),
                    amount_usd=amount_usd,
                    job_id=order.get("job_id"),
                    description=description,
                )
            print(f"\n✓ Order {order['order_id']} delivered.")

    except Exception as exc:
        order["status"] = "failed"
        order["error"] = str(exc)
        _save_order(order, work_dir)
        raise

    return order


# ─── Phase implementations ────────────────────────────────────────────────────

def _run_phase1_transcribe(order: dict, work_dir: Path) -> dict:
    audio_path = order.get("audio_path")

    # If audio_path is set but file is gone (e.g. ephemeral /tmp on web container),
    # fall through to drive_audio_id if available.
    if audio_path and not Path(audio_path).exists():
        print(f"  Phase 1: audio_path {audio_path} not found — trying drive_audio_id fallback")
        audio_path = None

    # Download from Drive file ID if available.
    if not audio_path and order.get("drive_audio_id"):
        from aiplatform.skills.storage.drive_read import drive_read
        suffix = order.get("audio_filename_suffix", ".mp3")
        audio_path = str(work_dir / f"audio{suffix}")
        print(f"  Phase 1: Downloading audio from Drive...")
        drive_read(order["drive_audio_id"], audio_path)
        order["audio_path"] = audio_path

    # Web UI orders supply audio_url instead of a local path — download it first.
    if not audio_path and order.get("audio_url"):
        import urllib.request
        audio_url = order["audio_url"]
        suffix = Path(audio_url.split("?")[0]).suffix or ".mp3"
        audio_path = str(work_dir / f"audio{suffix}")
        print(f"  Phase 1: Downloading audio from URL...")
        urllib.request.urlretrieve(audio_url, audio_path)
        order["audio_path"] = audio_path

    if not audio_path:
        if order.get("demo"):
            # No audio provided — use built-in demo transcript so the pipeline
            # can still generate a real-looking sample output.
            demo_transcript = (
                "Welcome to the show. Today we're exploring the latest discoveries in exoplanet research "
                "with a leading astrophysicist. We discuss the James Webb Space Telescope's findings, "
                "what makes a planet potentially habitable, and how machine learning is transforming the "
                "search for life beyond Earth. Our guest shares insights on the most promising exoplanet "
                "candidates, the challenges of detecting biosignatures across light-years, and what the "
                "next decade of space exploration holds. Whether you're a science enthusiast or a curious "
                "newcomer, this episode breaks down complex concepts into clear, engaging ideas. "
                "Key topics include: transit photometry, the habitable zone, atmospheric spectroscopy, "
                "TRAPPIST-1 system, and the Fermi paradox. Timestamps: [00:00] Introduction and guest "
                "background. [04:30] How the James Webb Telescope changed everything. [12:15] What makes "
                "a planet habitable? [21:00] Machine learning in the search for exoplanets. [33:45] "
                "Most promising candidates for life. [44:20] The Fermi paradox revisited. [52:00] "
                "What's next for space exploration. [58:30] Closing thoughts and resources."
            )
            demo_result = {
                "transcript": demo_transcript,
                "duration_seconds": 3600,
                "cost_usd": 0.0,
                "model": "demo",
            }
            (work_dir / "transcript.txt").write_text(demo_transcript, encoding="utf-8")
            _save_json(demo_result, work_dir / "transcript_data.json")
            return demo_result
        raise ValueError("Order must have either 'audio_path' or 'audio_url'")

    # ── Video → audio extraction (Service B) ─────────────────────────────────
    file_suffix = Path(audio_path).suffix.lower()
    if file_suffix in _VIDEO_EXTS:
        print(f"  Phase 1: Video detected ({file_suffix}) — extracting audio via FFmpeg...")
        from aiplatform.skills.media.extract_audio_from_video import extract_audio_from_video
        mp3_path = str(work_dir / "audio.mp3")
        extraction = extract_audio_from_video(audio_path, output_path=mp3_path)
        audio_path = extraction["audio_path"]
        order["audio_path"] = audio_path
        order["input_type"] = "video"
        print(f"    ✓ Audio extracted: {Path(audio_path).name}")
    else:
        order.setdefault("input_type", "audio")

    print(f"  Phase 1: Transcribing {Path(audio_path).name}...")

    result = transcribe_audio(audio_path)

    (work_dir / "transcript.txt").write_text(result["transcript"], encoding="utf-8")
    _save_json(result, work_dir / "transcript_data.json")

    log_cost(
        tool_id="openai-whisper-1",
        capability="transcription",
        cost_usd=result["cost_usd"],
        metadata={"order_id": order["order_id"], "duration_seconds": result["duration_seconds"]},
    )
    print(f"    ✓ {result['duration_seconds'] / 60:.1f} min transcribed — cost ${result['cost_usd']:.4f}")
    return result


def _run_phase2_generate(order: dict, transcript_data: dict, work_dir: Path = None) -> dict:
    service_type = order.get("service_type", "show_notes")
    tier = order["tier"]

    if service_type == "repurposing_pack":
        return _run_phase2_repurposing(order, transcript_data, work_dir)

    # ── Service A: Podcast Show Notes ────────────────────────────────────────
    print(f"  Phase 2: Generating {tier} show notes package...")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_message = build_content_prompt(order, transcript_data)

    max_tokens = (
        config.CLAUDE_MAX_TOKENS_PREMIUM if tier == "premium" else config.CLAUDE_MAX_TOKENS
    )
    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text
    content = parse_content_response(raw_text, tier)

    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )
    log_cost(
        tool_id=config.CLAUDE_MODEL,
        capability="content-generation",
        cost_usd=cost_usd,
        metadata={"order_id": order["order_id"], "tier": tier},
    )

    if work_dir:
        _save_json(content, work_dir / "content.json")
    print(f"    ✓ {len([v for v in content.values() if v])} sections generated — cost ${cost_usd:.4f}")
    return content


def _run_phase2_repurposing(order: dict, transcript_data: dict, work_dir: Path | None) -> dict:
    """Service B Phase 2: core generation (show notes + timestamps)."""
    tier = order.get("tier", "starter")
    print(f"  Phase 2: Generating repurposing pack core content ({tier})...")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_message = build_repurposing_prompt(order, transcript_data)

    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=config.CLAUDE_MAX_TOKENS,
        system=REPURPOSING_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    content = parse_repurposing_response(response.content[0].text)
    # Expose transcript in content dict for downstream packaging
    content["transcript"] = transcript_data.get("transcript", "")

    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )
    log_cost(
        tool_id=config.CLAUDE_MODEL,
        capability="content-generation",
        cost_usd=cost_usd,
        metadata={"order_id": order["order_id"], "tier": tier, "service": "repurposing_pack"},
    )

    if work_dir:
        _save_json(content, work_dir / "content.json")
    print(f"    ✓ Core content ready — cost ${cost_usd:.4f}")
    return content


def _run_phase2b_repurposing_extended(order: dict, content: dict, work_dir: Path) -> dict:
    """
    Service B Phase 2b: generate blog post, caption pack, and newsletter draft
    using dedicated platform skills. Results are attached to content dict.
    """
    tier = order.get("tier", "starter")
    tier_cfg = config.REPURPOSING_TIERS.get(tier, config.REPURPOSING_TIERS["starter"])
    outputs = tier_cfg.get("outputs", [])
    transcript = content.get("transcript", "")

    context = {
        "title":      order.get("episode_title", ""),
        "show_name":  order.get("show_name", ""),
        "host_name":  order.get("host_name", ""),
        "guest_name": order.get("guest_name", ""),
        "niche":      order.get("niche", "general"),
        "audience":   order.get("audience", "general audience"),
        "show_notes": content.get("show_notes", ""),
    }

    brand_voice = _load_brand_voice(order, work_dir)

    total_cost = 0.0

    if "blog_post" in outputs:
        print(f"  Phase 2b: Generating blog post...")
        word_range = tier_cfg.get("blog_word_range", (800, 1200))
        result = generate_blog_post(
            transcript=transcript,
            context=context,
            word_count_range=word_range,
            brand_voice_injection=brand_voice,
            max_tokens=4096,
        )
        content["blog_post_html"] = result.get("body_html", "")
        content["blog_post_text"] = result.get("body_text", "")
        content["blog_post_title"] = result.get("title", "")
        content["blog_meta_description"] = result.get("meta_description", "")
        content["blog_seo_tags"] = result.get("seo_tags", [])
        total_cost += result.get("cost_usd", 0)
        print(f"    ✓ Blog post ({result.get('word_count', 0)} words) — cost ${result.get('cost_usd', 0):.4f}")

    if "captions" in outputs:
        print(f"  Phase 2b: Generating caption pack...")
        platforms = tier_cfg.get("platforms", ["linkedin", "instagram", "twitter"])
        caption_count = tier_cfg.get("caption_count", 3)
        result = generate_caption_pack(
            transcript=transcript,
            context=context,
            platforms=platforms,
            captions_per_platform=caption_count,
            brand_voice_injection=brand_voice,
            max_tokens=4096,
        )
        content["captions"] = result.get("captions", {})
        total_cost += result.get("cost_usd", 0)
        platform_count = len(result.get("captions", {}))
        print(f"    ✓ Captions for {platform_count} platforms — cost ${result.get('cost_usd', 0):.4f}")

    if "newsletter" in outputs:
        print(f"  Phase 2b: Generating newsletter draft...")
        word_range = tier_cfg.get("newsletter_word_range", (300, 500))
        result = generate_newsletter_draft(
            transcript=transcript,
            context=context,
            word_count_range=word_range,
            brand_voice_injection=brand_voice,
            max_tokens=2048,
        )
        content["newsletter_subject_a"] = result.get("subject_a", "")
        content["newsletter_subject_b"] = result.get("subject_b", "")
        content["newsletter_preview"] = result.get("preview_text", "")
        content["newsletter_body_text"] = result.get("body_text", "")
        content["newsletter_body_html"] = result.get("body_html", "")
        total_cost += result.get("cost_usd", 0)
        print(f"    ✓ Newsletter draft ({result.get('word_count', 0)} words) — cost ${result.get('cost_usd', 0):.4f}")

    if total_cost > 0:
        log_cost(
            tool_id=config.CLAUDE_MODEL,
            capability="repurposing-extended",
            cost_usd=total_cost,
            metadata={"order_id": order["order_id"], "tier": tier},
        )

    _save_json(content, work_dir / "content.json")
    return content


def _load_brand_voice(order: dict, work_dir: Path) -> str:
    """Load cached brand voice injection string for a show, if available.
    Tries Redis first, falls back to local file for dev environments.
    """
    if not config.BRAND_VOICE_CACHE_ENABLED:
        return ""
    show_slug = order.get("show_name", "unknown").lower().replace(" ", "-")[:40]

    # Try Redis first
    r = _get_redis()
    if r:
        try:
            raw = r.get(f"content_studio:brand_voice:{show_slug}")
            if raw:
                cached = json.loads(raw)
                return cached.get("summary", {}).get("brand_voice_injection", "")
        except Exception as exc:
            logger.warning("Redis brand voice read failed (falling back to file): %s", exc)

    # Fall back to local file (dev / no Redis)
    cache_path = work_dir.parent / f"{show_slug}-brand-voice.json"
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return cached.get("summary", {}).get("brand_voice_injection", "")
        except Exception:
            return ""
    return ""


def _run_phase3_package(order: dict, content: dict, work_dir: Path) -> dict:
    print(f"  Phase 3: Building content package...")

    html = _build_doc_html(order, content)
    (work_dir / "content.html").write_text(html, encoding="utf-8")

    # PDF backup — full content package
    full_pdf_path = work_dir / f"{order['order_id']}-full.pdf"
    generate_full_pdf(order, content, full_pdf_path)
    print(f"    ✓ Full PDF: {full_pdf_path.name}")

    # Sample PDF — watermarked, for outreach / demos
    sample_pdf_path = work_dir / f"{order['order_id']}-sample.pdf"
    generate_sample_pdf(order, content, sample_pdf_path)
    order["sample_pdf_path"] = str(sample_pdf_path)
    print(f"    ✓ Sample PDF: {sample_pdf_path.name}")

    # Create per-order folder in Drive if configured
    folder_id = _get_or_create_order_folder(order["order_id"])

    # Set folder link immediately (before uploads, so it persists even if uploads fail)
    if folder_id:
        order["drive_folder_link"] = f"https://drive.google.com/drive/folders/{folder_id}"

    # Upload transcript + PDFs to Drive
    # Full order files → order folder; sample PDFs → dedicated samples folder
    transcript_path = work_dir / "transcript.txt"
    samples_folder = config.DRIVE_PODCAST_SAMPLES_ID or folder_id
    if folder_id:
        if transcript_path.exists():
            drive_write(transcript_path, folder_id, filename=f"{order['order_id']}-transcript.txt")
        drive_write(full_pdf_path, folder_id, filename=full_pdf_path.name)
    if samples_folder and sample_pdf_path.exists():
        res = drive_write(sample_pdf_path, samples_folder, filename=sample_pdf_path.name)
        order["drive_sample_pdf_link"] = res.get("web_view_link", "")

    doc_title = (
        f"{order.get('show_name', 'Podcast')} — "
        f"{order.get('episode_title', 'Episode')} "
        f"({order['tier'].title()} Package)"
    )

    gdoc: dict
    if folder_id or (config.DRIVE_PODCAST_ROOT_ID):
        gdoc = create_gdoc(
            title=doc_title,
            html_content=html,
            folder_id=folder_id or config.DRIVE_PODCAST_ROOT_ID,
            share_anyone_with_link=True,
        )
        print(f"    ✓ Google Doc ready: {gdoc['web_view_link']}")
    else:
        # Drive not configured — deliver local files only
        gdoc = {
            "web_view_link": f"file://{full_pdf_path.resolve()}",
            "doc_id": None,
        }
        print(f"    ✓ Local delivery only (Drive not configured)")
        print(f"      Full PDF:   {full_pdf_path}")
        print(f"      Sample PDF: {sample_pdf_path}")

    gdoc["full_pdf_path"] = str(full_pdf_path)
    gdoc["sample_pdf_path"] = str(sample_pdf_path)

    # Promote the GDoc link to a flat top-level key so the frontend can find it
    # (extractJobLinks checks order["gdoc_url"], not order["gdoc"]["web_view_link"])
    order["gdoc_url"] = gdoc.get("web_view_link", "")

    return gdoc


def _run_phase4_review(order: dict, gdoc: dict) -> None:
    print(f"  Phase 4: Review notification...")

    review_email = config.HUMAN_REVIEW_EMAIL
    if review_email:
        subject = f"[Review] {order.get('show_name')} — {order.get('episode_title')}"
        body = _review_email_html(order, gdoc)
        try:
            send_email(to=review_email, subject=subject, body_html=body)
            print(f"    ✓ Review email sent to {review_email}")
        except NotImplementedError:
            pass

    full_pdf = gdoc.get("full_pdf_path", "")
    sample_pdf = gdoc.get("sample_pdf_path", "")

    print(f"\n{'─' * 60}")
    print(f"REVIEW REQUIRED — Order: {order['order_id']}")
    print(f"Tier:       {order['tier'].upper()}")
    print(f"Episode:    {order.get('episode_title')}")
    print(f"Google Doc: {gdoc['web_view_link']}")
    if full_pdf:
        print(f"Full PDF:   {full_pdf}")
    if sample_pdf:
        print(f"Sample PDF: {sample_pdf}")
    print(f"{'─' * 60}\n")


def _run_phase5_deliver(order: dict, gdoc: dict) -> None:
    print(f"  Phase 5: Delivering to client...")

    client_email = order.get("client_email", "")
    if client_email:
        subject = f"Your Podcast Content Package — {order.get('episode_title')}"
        body = _delivery_email_html(order, gdoc)
        try:
            send_email(to=client_email, subject=subject, body_html=body)
            print(f"    ✓ Delivery email sent to {client_email}")
        except NotImplementedError:
            print(f"    ⚠  Email skill not yet active — delivery link: {gdoc['web_view_link']}")
    else:
        print(f"    ✓ Delivery link: {gdoc['web_view_link']}")


# ─── Add-on runner ────────────────────────────────────────────────────────────

# Supported add-on IDs — map to their runner function
_ADDON_RUNNERS = {}  # populated below after function definitions


def _run_addons(order: dict, content: dict, work_dir: Path) -> dict:
    """
    Run all requested add-ons for an order.
    Returns a dict of {addon_id: result_or_error}.
    """
    add_ons = order.get("add_ons") or []
    results = {}
    for addon_id in add_ons:
        runner = _ADDON_RUNNERS.get(addon_id)
        if not runner:
            results[addon_id] = {"error": f"Unknown add-on: {addon_id}"}
            print(f"    ⚠  Unknown add-on: {addon_id}")
            continue
        print(f"  Add-on: {addon_id}...")
        try:
            result = runner(order, content, work_dir)
            results[addon_id] = result
            cost = result.get("cost_usd", 0)
            print(f"    ✓ {addon_id} complete — cost ${cost:.4f}")
            log_cost(
                tool_id=config.CLAUDE_MODEL,
                capability=f"addon-{addon_id}",
                cost_usd=cost,
                metadata={"order_id": order["order_id"], "addon": addon_id},
            )
        except Exception as exc:
            results[addon_id] = {"error": str(exc)}
            print(f"    ✗ {addon_id} failed: {exc}")
    return results


def _run_addon_brand_voice(order: dict, content: dict, work_dir: Path) -> dict:
    """
    Add-on: brand-voice
    Analyses the current episode transcript (plus any extra transcripts in the order)
    and produces a Brand Voice Guide, cached per show.
    """
    transcripts = []
    # Primary transcript from this order
    primary = (content.get("transcript") or order.get("transcript_data", {}).get("transcript") or "").strip()
    if primary:
        transcripts.append(primary)
    # Extra transcripts supplied via order dict (e.g. from CLI --extra-transcripts)
    for extra in (order.get("extra_transcripts") or []):
        path = Path(extra)
        if path.exists():
            transcripts.append(path.read_text(encoding="utf-8"))

    if not transcripts:
        raise ValueError("No transcript available for brand-voice add-on.")

    # Cache key: per-show, not per-episode
    show_slug = order.get("show_name", "unknown").lower().replace(" ", "-")[:40]
    local_cache_path = (work_dir.parent / f"{show_slug}-brand-voice.json") if config.BRAND_VOICE_CACHE_ENABLED else None

    result = generate_brand_voice(
        transcripts=transcripts,
        show_name=order.get("show_name", ""),
        niche=order.get("niche", "general"),
        audience=order.get("audience", "general audience"),
        host_name=order.get("host_name", ""),
        cache_path=local_cache_path,  # local file fallback for dev
    )

    # Persist to Redis (primary) — survives container restarts and multi-instance deploys
    if config.BRAND_VOICE_CACHE_ENABLED:
        r = _get_redis()
        if r:
            try:
                r.set(
                    f"content_studio:brand_voice:{show_slug}",
                    json.dumps(result),
                    ex=_BRAND_VOICE_TTL,
                )
            except Exception as exc:
                logger.warning("Redis brand voice write failed (local file still saved): %s", exc)

    # Save the guide as a text file alongside the order
    guide_path = work_dir / f"{order['order_id']}-brand-voice.txt"
    guide_path.write_text(result["guide"], encoding="utf-8")
    result["guide_path"] = str(guide_path)
    return result


def _run_addon_promo_copy(order: dict, content: dict, work_dir: Path) -> dict:
    """
    Add-on: promo-copy
    Generates platform description, audiogram caption, newsletter teaser, LinkedIn post.
    Injects cached brand voice if available.
    """
    # Try to load brand voice injection from cache (Redis → local file fallback)
    brand_voice_injection = _load_brand_voice(order, work_dir)

    transcript = (
        content.get("transcript")
        or order.get("transcript_data", {}).get("transcript")
        or ""
    )

    episode_context = {
        "show_name":              order.get("show_name", ""),
        "episode_title":          order.get("episode_title", ""),
        "host_name":              order.get("host_name", ""),
        "niche":                  order.get("niche", "general"),
        "audience":               order.get("audience", "general audience"),
        "transcript":             transcript,
        "show_notes":             content.get("show_notes", ""),
        "brand_voice_injection":  brand_voice_injection,
    }

    result = generate_promo_copy(episode_context)

    # Save all four pieces as a single text file
    promo_path = work_dir / f"{order['order_id']}-promo-copy.txt"
    promo_path.write_text(_format_promo_output(result), encoding="utf-8")
    result["promo_path"] = str(promo_path)
    return result


def _format_promo_output(pieces: dict) -> str:
    sections = [
        ("PLATFORM DESCRIPTION", "platform_description"),
        ("AUDIOGRAM CAPTION",    "audiogram_caption"),
        ("NEWSLETTER TEASER",    "newsletter_teaser"),
        ("LINKEDIN POST",        "linkedin_post"),
    ]
    lines = []
    for label, key in sections:
        lines += [f"{'─' * 60}", f"{label}", f"{'─' * 60}", "", pieces.get(key, ""), ""]
    return "\n".join(lines)


def _run_addon_social_calendar(order: dict, content: dict, work_dir: Path) -> dict:
    """
    Add-on: social-calendar
    Generates a 30-day social media calendar from the current episode transcript.
    Up to 3 additional transcript files can be supplied via order["extra_transcripts"].
    """
    transcripts = []
    primary = (content.get("transcript") or order.get("transcript_data", {}).get("transcript") or "").strip()
    if primary:
        transcripts.append(primary)
    for extra in (order.get("extra_transcripts") or []):
        path = Path(extra)
        if path.exists():
            transcripts.append(path.read_text(encoding="utf-8"))

    if not transcripts:
        raise ValueError("No transcript available for social-calendar add-on.")

    episode_context = {
        "show_name": order.get("show_name", ""),
        "niche":     order.get("niche", "general"),
        "audience":  order.get("audience", "general audience"),
        "host_name": order.get("host_name", ""),
    }

    platforms = (
        [p.strip() for p in order.get("social_platforms", "").split(",") if p.strip()]
        or config.CAPTION_PLATFORMS_DEFAULT
    )

    brand_voice = _load_brand_voice(order, work_dir)

    result = generate_social_calendar(
        transcripts=transcripts,
        episode_context=episode_context,
        brand_voice_injection=brand_voice,
        platforms=platforms,
        max_tokens=8192,
    )

    # Save as text table
    cal_path = work_dir / f"{order['order_id']}-social-calendar.txt"
    cal_path.write_text(_format_calendar_output(result["calendar"]), encoding="utf-8")
    result["calendar_path"] = str(cal_path)
    return result


def _run_addon_email_sequence(order: dict, content: dict, work_dir: Path) -> dict:
    """
    Add-on: email-sequence
    Generates a 5-email welcome/nurture sequence for new podcast subscribers.
    """
    transcripts = []
    primary = (content.get("transcript") or order.get("transcript_data", {}).get("transcript") or "").strip()
    if primary:
        transcripts.append(primary)
    for extra in (order.get("extra_transcripts") or []):
        path = Path(extra)
        if path.exists():
            transcripts.append(path.read_text(encoding="utf-8"))

    if not transcripts:
        raise ValueError("No transcript available for email-sequence add-on.")

    episode_context = {
        "show_name": order.get("show_name", ""),
        "niche":     order.get("niche", "general"),
        "audience":  order.get("audience", "general audience"),
        "host_name": order.get("host_name", ""),
    }

    brand_voice = _load_brand_voice(order, work_dir)
    sequence_length = int(order.get("email_sequence_length", 5))

    result = generate_email_sequence(
        transcripts=transcripts,
        episode_context=episode_context,
        brand_voice_injection=brand_voice,
        sequence_length=sequence_length,
        max_tokens=6144,
    )

    seq_path = work_dir / f"{order['order_id']}-email-sequence.txt"
    seq_path.write_text(_format_email_sequence_output(result["emails"]), encoding="utf-8")
    result["sequence_path"] = str(seq_path)
    return result


def _format_calendar_output(calendar: list[dict]) -> str:
    lines = [f"{'Day':<5} {'Platform':<12} {'Pillar':<20} {'Hook':<60} Post"]
    lines.append("─" * 120)
    for entry in calendar:
        hook = entry.get("hook", "")[:57] + "..." if len(entry.get("hook", "")) > 60 else entry.get("hook", "")
        lines.append(
            f"{entry['day']:<5} {entry.get('platform',''):<12} {entry.get('pillar',''):<20} {hook:<60}"
        )
        lines.append(f"       {entry.get('post', '')}")
        lines.append(f"       {entry.get('hashtags', '')}")
        lines.append("")
    return "\n".join(lines)


def _format_email_sequence_output(emails: list[dict]) -> str:
    parts = []
    for email in emails:
        day_map = {1: 0, 2: 2, 3: 5, 4: 9, 5: 14, 6: 21, 7: 30}
        send_day = day_map.get(email["number"], (email["number"] - 1) * 3)
        parts.append(f"{'─' * 60}")
        parts.append(f"EMAIL {email['number']} — Send Day {send_day}")
        parts.append(f"Subject:      {email.get('subject', '')}")
        parts.append(f"Preview Text: {email.get('preview_text', '')}")
        parts.append(f"")
        parts.append(email.get("body_text", ""))
        parts.append(f"")
    return "\n".join(parts)


def _run_addon_guest_outreach(order: dict, content: dict, work_dir: Path) -> dict:
    """
    Add-on: guest-outreach
    Generates 3 email templates (cold/warm/follow-up) for pitching podcast guests.
    """
    episode_context = {
        "show_name":  order.get("show_name", ""),
        "niche":      order.get("niche", "general"),
        "audience":   order.get("audience", "general audience"),
        "host_name":  order.get("host_name", ""),
        "show_notes": content.get("show_notes", ""),
    }

    result = generate_guest_outreach(
        episode_context=episode_context,
        guest_name=order.get("guest_name", ""),
        guest_expertise=order.get("guest_expertise", ""),
        max_tokens=4096,
    )

    out_path = work_dir / f"{order['order_id']}-guest-outreach.txt"
    out_path.write_text(_format_outreach_output(result["templates"]), encoding="utf-8")
    result["outreach_path"] = str(out_path)
    return result


def _run_addon_landing_audit(order: dict, content: dict, work_dir: Path) -> dict:
    """
    Add-on: landing-audit
    Fetches show_url and produces a scored CRO audit report.
    Requires order["show_url"] to be set.
    """
    show_url = order.get("show_url", "").strip()
    if not show_url:
        raise ValueError(
            "landing-audit add-on requires 'show_url' in the order. "
            "Add the podcast website URL to the order form."
        )

    page_context = {
        "show_name": order.get("show_name", ""),
        "niche":     order.get("niche", "general"),
        "audience":  order.get("audience", "general audience"),
    }

    try:
        result = audit_landing_page(
            url=show_url,
            page_context=page_context,
            max_tokens=6144,
        )
    except (FetchError, PageTooLarge) as exc:
        raise ValueError(f"Could not audit {show_url}: {exc}") from exc

    out_path = work_dir / f"{order['order_id']}-landing-audit.txt"
    out_path.write_text(result["raw_report"], encoding="utf-8")
    result["audit_path"] = str(out_path)

    summary_lines = [
        f"Overall Score: {result['overall_score']}/10",
        "",
        "Section Scores:",
    ]
    for s in result["sections"]:
        score_str = f"{s['score']}/10" if s["score"] is not None else "n/a"
        summary_lines.append(f"  {s['name']:<16} {score_str}")
    print("    " + "\n    ".join(summary_lines))

    return result


def _format_outreach_output(templates: list[dict]) -> str:
    parts = []
    for t in templates:
        parts.append(f"{'─' * 60}")
        parts.append(f"{t.get('type', '').upper()}")
        parts.append(f"{'─' * 60}")
        parts.append(f"Subject: {t.get('subject', '')}")
        parts.append("")
        parts.append(t.get("body", ""))
        guide = t.get("personalisation_guide", "")
        if guide:
            parts.append("")
            parts.append("PERSONALISATION GUIDE:")
            parts.append(guide)
        parts.append("")
    return "\n".join(parts)


def _run_addon_launch_playbook(order: dict, content: dict, work_dir: Path) -> dict:
    """
    Add-on: launch-playbook
    Generates an 8-week podcast launch plan.
    """
    show_context = {
        "show_name":       order.get("show_name", ""),
        "niche":           order.get("niche", "general"),
        "audience":        order.get("audience", "general audience"),
        "host_name":       order.get("host_name", ""),
        "show_concept":    order.get("show_concept", ""),
        "host_background": order.get("host_background", ""),
        "launch_type":     order.get("launch_type", "new"),
    }

    result = generate_launch_playbook(show_context=show_context, max_tokens=10000)

    out_path = work_dir / f"{order['order_id']}-launch-playbook.txt"
    out_path.write_text(result["raw_playbook"], encoding="utf-8")
    result["playbook_path"] = str(out_path)
    return result


def _run_addon_competitive_analysis(order: dict, content: dict, work_dir: Path) -> dict:
    """
    Add-on: competitive-analysis
    Benchmarks the show against up to 3 competitor show URLs.
    Requires order["competitor_urls"] (comma-separated or list).
    """
    raw_urls = order.get("competitor_urls", "")
    if isinstance(raw_urls, str):
        competitor_urls = [u.strip() for u in raw_urls.split(",") if u.strip()]
    else:
        competitor_urls = list(raw_urls)

    if not competitor_urls:
        raise ValueError(
            "competitive-analysis add-on requires 'competitor_urls' in the order. "
            "Add up to 3 competitor show website URLs (comma-separated)."
        )

    show_context = {
        "show_name":  order.get("show_name", ""),
        "niche":      order.get("niche", "general"),
        "audience":   order.get("audience", "general audience"),
        "host_name":  order.get("host_name", ""),
        "show_notes": content.get("show_notes", ""),
    }

    brand_voice = _load_brand_voice(order, work_dir)

    result = generate_competitive_analysis(
        show_context=show_context,
        competitor_urls=competitor_urls,
        brand_voice_injection=brand_voice,
        max_tokens=8192,
    )

    out_path = work_dir / f"{order['order_id']}-competitive-analysis.txt"
    out_path.write_text(result["raw_report"], encoding="utf-8")
    result["analysis_path"] = str(out_path)

    print(
        f"    Competitors analysed: {len(competitor_urls)} | "
        f"Content gaps: {len(result.get('content_gaps', []))} | "
        f"Tactics: {len(result.get('steal_worthy_tactics', []))}"
    )
    return result


# Register runners
_ADDON_RUNNERS["brand-voice"]          = _run_addon_brand_voice
_ADDON_RUNNERS["promo-copy"]           = _run_addon_promo_copy
_ADDON_RUNNERS["social-calendar"]      = _run_addon_social_calendar
_ADDON_RUNNERS["email-sequence"]       = _run_addon_email_sequence
_ADDON_RUNNERS["guest-outreach"]       = _run_addon_guest_outreach
_ADDON_RUNNERS["landing-audit"]        = _run_addon_landing_audit
_ADDON_RUNNERS["launch-playbook"]      = _run_addon_launch_playbook
_ADDON_RUNNERS["competitive-analysis"] = _run_addon_competitive_analysis


# ─── HTML builder ─────────────────────────────────────────────────────────────

def _build_doc_html(order: dict, content: dict) -> str:
    service_type = order.get("service_type", "show_notes")
    if service_type == "repurposing_pack":
        return _build_repurposing_doc_html(order, content)
    return _build_show_notes_doc_html(order, content)


def _build_show_notes_doc_html(order: dict, content: dict) -> str:
    tier = order["tier"]
    show = order.get("show_name", "Podcast")
    episode = order.get("episode_title", "Episode")
    host = order.get("host_name", "")

    def section(title: str, key: str) -> str:
        body = content.get(key, "")
        if not body:
            return ""
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        inner = "".join(
            f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs
        )
        return f"<h2>{title}</h2>{inner}"

    sections_html = ""
    sections_html += section("Show Notes", "show_notes")
    sections_html += section("Timestamps", "timestamps")
    sections_html += section("Guest Bio", "guest_bio")
    if "transcript" in content:
        sections_html += section("Full Transcript", "transcript")
    if "social_captions" in content:
        sections_html += section("Social Media Captions", "social_captions")
    if "newsletter_excerpt" in content:
        sections_html += section("Newsletter Excerpt", "newsletter_excerpt")
    if "seo_metadata" in content:
        sections_html += section("SEO Metadata", "seo_metadata")

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{episode}</title></head>
<body>
<h1>{episode}</h1>
<p><em>{show}{f" | Host: {host}" if host else ""} | {tier.title()} Package</em></p>
<hr>
{sections_html}
<hr>
<p><small>Generated by EchoForge Content Studio &mdash; echoforge.biz</small></p>
</body>
</html>"""


def _build_repurposing_doc_html(order: dict, content: dict) -> str:
    """Build the Google Doc HTML for a Service B (Content Repurposing Pack) order."""
    episode = order.get("episode_title", "Episode")
    show = order.get("show_name", "")
    host = order.get("host_name", "")
    tier = order.get("tier", "starter").title()
    input_type = order.get("input_type", "audio").title()

    def section(title: str, body: str) -> str:
        if not body:
            return ""
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        inner = "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)
        return f"<h2>{title}</h2>{inner}"

    sections_html = ""
    sections_html += section("Show Notes / Content Summary", content.get("show_notes", ""))
    sections_html += section("Timestamps", content.get("timestamps", ""))
    sections_html += section("Full Transcript", content.get("transcript", ""))

    # Blog post
    if content.get("blog_post_html"):
        sections_html += (
            f"<h2>Blog Post — {content.get('blog_post_title', 'Article')}</h2>"
            f"<p><em>Meta: {content.get('blog_meta_description', '')}</em></p>"
            + content["blog_post_html"]
        )

    # Social captions
    captions = content.get("captions", {})
    if captions:
        cap_html = "<h2>Social Media Caption Pack</h2>"
        platform_labels = {
            "linkedin": "LinkedIn", "instagram": "Instagram",
            "twitter": "Twitter/X", "tiktok": "TikTok", "youtube": "YouTube",
        }
        for platform, variants in captions.items():
            label = platform_labels.get(platform, platform.title())
            cap_html += f"<h3>{label}</h3>"
            for i, variant in enumerate(variants, 1):
                paragraphs = [p.strip() for p in variant.split("\n\n") if p.strip()]
                inner = "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)
                cap_html += f"<p><strong>Variant {i}:</strong></p>{inner}"
        sections_html += cap_html

    # Newsletter
    if content.get("newsletter_body_html"):
        sections_html += (
            "<h2>Newsletter Draft</h2>"
            f"<p><strong>Subject A:</strong> {content.get('newsletter_subject_a', '')}</p>"
            f"<p><strong>Subject B:</strong> {content.get('newsletter_subject_b', '')}</p>"
            f"<p><em>Preview: {content.get('newsletter_preview', '')}</em></p>"
            + content["newsletter_body_html"]
        )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{episode} — Content Repurposing Pack</title></head>
<body>
<h1>{episode}</h1>
<p><em>{show}{f" | {host}" if host else ""} | {tier} Repurposing Pack | Input: {input_type}</em></p>
<hr>
{sections_html}
<hr>
<p><small>Generated by EchoForge Content Studio &mdash; echoforge.biz</small></p>
</body>
</html>"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_or_create_order_folder(order_id: str) -> str | None:
    """Create a per-order subfolder in Drive. Returns folder_id or None if not configured."""
    parent = config.DRIVE_PODCAST_ORDERS_ID
    if not parent:
        return None
    try:
        result = create_folder(name=order_id, parent_id=parent)
        return result["folder_id"]
    except Exception:
        return None




def work_dir_for(order: dict, base: str = "./output/content_studio") -> Path:
    return Path(base) / order["order_id"]


def _save_order(order: dict, work_dir: Path) -> None:
    _save_json(order, work_dir / "order.json")
    try:
        from aiplatform.database.job_ops import upsert_job
        upsert_job(order, "content_studio")
    except Exception:
        pass  # non-blocking — JSON file is still the source of truth


def _save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _review_email_html(order: dict, gdoc: dict) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:16px">
<p>A new podcast content package is ready for review.</p>
<table cellpadding="4">
  <tr><td><b>Order</b></td><td>{order['order_id']}</td></tr>
  <tr><td><b>Show</b></td><td>{order.get('show_name')}</td></tr>
  <tr><td><b>Episode</b></td><td>{order.get('episode_title')}</td></tr>
  <tr><td><b>Tier</b></td><td>{order['tier'].upper()}</td></tr>
</table>
<p><a href="{gdoc['web_view_link']}">Open Google Doc for review &rarr;</a></p>
<p>Approve or reject the order in the <a href="https://planBadmin.com">admin dashboard</a>.</p>
</body></html>"""


def _delivery_email_html(order: dict, gdoc: dict) -> str:
    service_type = order.get("service_type", "show_notes")
    tier = order.get("tier", "")

    if service_type == "repurposing_pack":
        tier_cfg = config.REPURPOSING_TIERS.get(tier, {})
        tier_desc = tier_cfg.get("description", "Content Repurposing Pack")
        outputs = tier_cfg.get("outputs", [])
        output_lines = ""
        output_map = {
            "transcript":        "Full transcript",
            "show_notes":        "Show notes / content summary",
            "timestamps":        "Timestamps / chapter markers",
            "captions":          "Social media caption pack",
            "blog_post":         "SEO blog post",
            "newsletter":        "Newsletter draft (with subject line A/B)",
            "linkedin_longform": "LinkedIn long-form post",
            "youtube_description": "YouTube description",
        }
        for key in outputs:
            label = output_map.get(key, key)
            output_lines += f"<li>{label}</li>"

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:16px">
<p>Hi,</p>
<p>Your <b>Content Repurposing Pack</b> for <b>{order.get('episode_title')}</b> is ready!</p>
<p><b>What's included ({tier.title()} tier):</b></p>
<ul>{output_lines}</ul>
<p><a href="{gdoc['web_view_link']}" style="font-size:16px;font-weight:bold;color:#1a56db;">Access your Google Doc &rarr;</a></p>
<p>This document has been human-reviewed before delivery. If you'd like any edits,
please reply to this email.</p>
<p>Thanks,<br>EchoForge Content Studio<br>echoforge.biz</p>
</body></html>"""

    # Service A: Podcast Show Notes
    tier_desc = config.TIERS.get(tier, {}).get("description", "")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:16px">
<p>Hi,</p>
<p>Your podcast content package for <b>{order.get('episode_title')}</b> is ready!</p>
<p><b>What's included ({tier_desc}):</b></p>
<p><a href="{gdoc['web_view_link']}" style="font-size:16px;font-weight:bold;color:#1a56db;">Access your Google Doc &rarr;</a></p>
<p>The document is view-only. If you'd like to request edits or have questions,
please reply to this email.</p>
<p>Thanks,<br>EchoForge Content Studio<br>echoforge.biz</p>
</body></html>"""
