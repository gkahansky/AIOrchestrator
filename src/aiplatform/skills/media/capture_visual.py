"""
Platform skill: capture_visual

Captures visual content for embedding in research documents:
  - screenshot_url()   — takes a Playwright screenshot of a live URL
  - generate_chart()   — generates a chart/diagram via Gemini Imagen

Both return {"image_path": str, "success": bool, "error": str | None}.
On failure they return success=False without raising, so the caller can
embed the visual when available and silently skip it when not.

Venture-agnostic.
"""

import os
import uuid
from pathlib import Path


def screenshot_url(
    url: str,
    output_path: str,
    width: int = 1280,
    height: int = 900,
    wait_ms: int = 2500,
) -> dict:
    """
    Take a viewport screenshot of a URL using Playwright (headless Chromium).

    Uses domcontentloaded + a brief wait so JS-rendered pages have time to paint.
    Full-page scroll is intentionally disabled — we want the "above the fold" view
    that a visitor would see, not a giant concatenated screenshot.

    Args:
        url:         Full URL to screenshot (must include https://).
        output_path: Where to save the PNG.
        width:       Viewport width in pixels (default 1280).
        height:      Viewport height in pixels (default 900).
        wait_ms:     Milliseconds to wait after load before screenshotting.

    Returns:
        {"image_path": str, "success": bool, "error": str | None}
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            page = browser.new_page(
                viewport={"width": width, "height": height},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page.goto(url, timeout=20_000, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)

            # Dismiss cookie banners etc. by pressing Escape
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass

            page.screenshot(path=output_path, full_page=False, type="png")
            browser.close()

        return {"image_path": output_path, "success": True, "error": None}

    except Exception as exc:
        return {"image_path": output_path, "success": False, "error": str(exc)}


def generate_chart(
    description: str,
    output_path: str,
    google_ai_api_key: str | None = None,
    mode: str = "chart",
) -> dict:
    """
    Generate an image using Gemini Imagen.

    Args:
        description:       Natural-language description of what to generate.
        output_path:       Where to save the PNG.
        google_ai_api_key: GOOGLE_AI_API_KEY override; falls back to env var.
        mode:              "chart"  — data visualisation (bar charts, funnels, matrices).
                           "ui"     — website/app UI mockup (used as screenshot fallback).

    Returns:
        {"image_path": str, "success": bool, "error": str | None}
    """
    api_key = google_ai_api_key or os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        return {
            "image_path": output_path,
            "success": False,
            "error": "GOOGLE_AI_API_KEY not configured",
        }

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        if mode == "ui":
            prompt = (
                f"Realistic mockup of a website or web application UI for a business "
                f"market research report. {description}. "
                f"Clean, modern design. Desktop browser viewport. Crisp text and UI "
                f"elements. Professional SaaS or marketing website aesthetic. "
                f"No browser chrome. No watermarks."
            )
        else:
            prompt = (
                f"Professional data visualization for a business market research report. "
                f"{description}. "
                f"Clean, minimal design. White background. High contrast colours suitable "
                f"for print. Clearly labelled axes and legends. No decorative elements. "
                f"Business presentation quality. No watermarks."
            )

        response = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="4:3",
                output_mime_type="image/png",
                safety_filter_level="BLOCK_LOW_AND_ABOVE",
                person_generation="DONT_ALLOW",
            ),
        )

        if not response.generated_images:
            return {"image_path": output_path, "success": False, "error": "No image returned"}

        Path(output_path).write_bytes(response.generated_images[0].image.image_bytes)
        return {"image_path": output_path, "success": True, "error": None}

    except Exception as exc:
        return {"image_path": output_path, "success": False, "error": str(exc)}
