"""
Content Studio pipeline — podcast show notes + marketing content delivery.

Phases:
    1 — Transcription           (OpenAI Whisper)
    2 — Content Generation      (Claude API, tier-aware)
    3 — Packaging               (Google Doc creation)
    4 — Human Review ★          (email notification + approval gate)
    5 — Delivery                (send Google Doc link to client)

Order status state machine:
    pending → transcribing → transcribed → generating → generated →
    packaging → packaged → review_pending → approved →
    delivering → delivered
              └→ revision_requested → re_delivering → delivered
              └→ failed
"""

import json
import os
from datetime import datetime
from pathlib import Path

import anthropic

from aiplatform.skills.media.transcribe_audio import transcribe_audio
from aiplatform.skills.media.generate_brand_voice import generate_brand_voice
from aiplatform.skills.media.generate_promo_copy import generate_promo_copy
from aiplatform.skills.storage.create_gdoc import create_gdoc
from aiplatform.skills.storage.drive_organise import create_folder
from aiplatform.skills.storage.drive_write import drive_write
from aiplatform.skills.comms.send_email import send_email
from aiplatform.skills.finance.log_cost import log_cost
from ventures.content_studio import config
from ventures.content_studio.content_pdf import generate_full_pdf, generate_sample_pdf
from ventures.content_studio.prompts import SYSTEM_PROMPT, build_content_prompt, parse_content_response


def run_order(order: dict, output_dir: str = "./output/content_studio") -> dict:
    """
    Run all pipeline phases for a single order.
    Saves order state after each phase — safe to re-run from any checkpoint.

    Returns the updated order dict.
    """
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
            # Pipeline pauses here — approval sets status to "approved" externally
            # or AUTO_APPROVE bypasses the gate
            if config.AUTO_APPROVE:
                order["status"] = "approved"
                _save_order(order, work_dir)
            else:
                print(f"\nPipeline paused at review gate.")
                print(f"Set order status to 'approved' in {work_dir / 'order.json'} to continue.\n")
                return order

        # ── Phase 5: Delivery ──────────────────────────────────────────────────
        if order["status"] == "approved":
            order["status"] = "delivering"
            _save_order(order, work_dir)
            _run_phase5_deliver(order, gdoc)
            order["status"] = "delivered"
            order["delivered_at"] = datetime.utcnow().isoformat()
            _save_order(order, work_dir)
            print(f"\n✓ Order {order['order_id']} delivered.")

    except Exception as exc:
        order["status"] = "failed"
        order["error"] = str(exc)
        _save_order(order, work_dir)
        raise

    return order


# ─── Phase implementations ────────────────────────────────────────────────────

def _run_phase1_transcribe(order: dict, work_dir: Path) -> dict:
    audio_path = order["audio_path"]
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
    tier = order["tier"]
    print(f"  Phase 2: Generating {tier} content package...")

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

    # Claude Sonnet 4.6 pricing: $3/M input, $15/M output tokens
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
    print(f"    ✓ Sample PDF: {sample_pdf_path.name}")

    # Create per-order folder in Drive if configured
    folder_id = _get_or_create_order_folder(order["order_id"])

    # Upload transcript + PDFs to Drive
    transcript_path = work_dir / "transcript.txt"
    if folder_id:
        if transcript_path.exists():
            drive_write(transcript_path, folder_id, filename=f"{order['order_id']}-transcript.txt")
        drive_write(full_pdf_path, folder_id, filename=full_pdf_path.name)
        drive_write(sample_pdf_path, folder_id, filename=sample_pdf_path.name)

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
            share_anyone_with_link=False,
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

    # Cache path: per-show, not per-episode
    cache_path = None
    if config.BRAND_VOICE_CACHE_ENABLED:
        show_slug = order.get("show_name", "unknown").lower().replace(" ", "-")[:40]
        cache_path = work_dir.parent / f"{show_slug}-brand-voice.json"

    result = generate_brand_voice(
        transcripts=transcripts,
        show_name=order.get("show_name", ""),
        niche=order.get("niche", "general"),
        audience=order.get("audience", "general audience"),
        host_name=order.get("host_name", ""),
        cache_path=cache_path,
    )

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
    # Try to load brand voice injection from cache
    brand_voice_injection = ""
    if config.BRAND_VOICE_CACHE_ENABLED:
        show_slug = order.get("show_name", "unknown").lower().replace(" ", "-")[:40]
        cache_path = work_dir.parent / f"{show_slug}-brand-voice.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            brand_voice_injection = cached.get("summary", {}).get("brand_voice_injection", "")

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


# Register runners
_ADDON_RUNNERS["brand-voice"] = _run_addon_brand_voice
_ADDON_RUNNERS["promo-copy"]  = _run_addon_promo_copy


# ─── HTML builder ─────────────────────────────────────────────────────────────

def _build_doc_html(order: dict, content: dict) -> str:
    tier = order["tier"]
    show = order.get("show_name", "Podcast")
    episode = order.get("episode_title", "Episode")
    host = order.get("host_name", "")

    def section(title: str, key: str) -> str:
        body = content.get(key, "")
        if not body:
            return ""
        # Convert plain newlines to <br> inside <p>, preserve paragraphs
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        inner = "".join(
            f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs
        )
        return f"<h2>{title}</h2>{inner}"

    tier_label = f"{tier.title()} Package"

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
<p><em>{show}{f" | Host: {host}" if host else ""} | {tier_label}</em></p>
<hr>
{sections_html}
<hr>
<p><small>Generated by Echoforge Content Studio &mdash; echoforge.biz</small></p>
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


def _save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _review_email_html(order: dict, gdoc: dict) -> str:
    return f"""
<p>A new podcast content package is ready for review.</p>
<table>
  <tr><td><b>Order</b></td><td>{order['order_id']}</td></tr>
  <tr><td><b>Show</b></td><td>{order.get('show_name')}</td></tr>
  <tr><td><b>Episode</b></td><td>{order.get('episode_title')}</td></tr>
  <tr><td><b>Tier</b></td><td>{order['tier'].upper()}</td></tr>
</table>
<p><a href="{gdoc['web_view_link']}">Open Google Doc for review &rarr;</a></p>
<p>To approve: set status to "approved" in the order JSON and re-run the pipeline,
or reply APPROVE to this email (Sprint 2+).</p>
"""


def _delivery_email_html(order: dict, gdoc: dict) -> str:
    tier_desc = config.TIERS[order["tier"]]["description"]
    return f"""
<p>Hi,</p>
<p>Your podcast content package for <b>{order.get('episode_title')}</b> is ready!</p>
<p><b>What's included ({tier_desc}):</b></p>
<p><a href="{gdoc['web_view_link']}">Access your Google Doc &rarr;</a></p>
<p>The document is view-only. If you'd like to request edits or have questions,
please reply to this email.</p>
<p>Thanks,<br>Echoforge Content Studio<br>echoforge.biz</p>
"""
