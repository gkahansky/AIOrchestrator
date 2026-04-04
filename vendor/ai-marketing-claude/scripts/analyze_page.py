#!/usr/bin/env python3
"""
Marketing Page Analyzer — Multi-page site crawler.

Crawls up to MAX_PAGES internal links from the target domain, merges all
findings, then scores the whole site.  A single-page scan is a known source
of false negatives (contact forms, testimonials, about pages all missed) so
we follow internal links breadth-first before scoring.
"""

import sys
import json
import urllib.request
import urllib.error
import ssl
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin, urlunparse

# ── Crawler settings ──────────────────────────────────────────────────────────
MAX_PAGES = 20          # Maximum pages crawled per domain
PAGE_TIMEOUT = 10       # Seconds per page fetch (keep total run time sane)

# File extensions that are never HTML — skip without fetching
_SKIP_EXT = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".zip", ".gz", ".tar", ".doc", ".docx", ".xls", ".xlsx",
    ".mp3", ".mp4", ".webm", ".ogg", ".wav",
    ".ico", ".woff", ".woff2", ".ttf", ".eot", ".css", ".js", ".json", ".xml",
}

# URL path patterns that are almost certainly not content pages
_SKIP_PATTERNS = ("/wp-admin", "/wp-json", "/wp-content", "/.well-known", "/feed", "/rss")

# Link href / URL patterns that indicate a contact / CTA destination
# (language-agnostic — matched against lowercased href)
_CONTACT_HREF_PATTERNS = [
    "contact", "קשר", "form", "book", "schedule", "quote",
    "consult", "appointment", "touch", "reach", "enquir", "inquir",
    "signup", "sign-up", "register", "subscribe", "demo", "trial",
]

# English CTA phrases detected in link / button text
_CTA_TEXT_WORDS = [
    "sign up", "get started", "try free", "start free", "buy now",
    "subscribe", "join", "register", "download", "book", "schedule",
    "request demo", "contact us", "learn more", "see pricing",
    "start trial", "create account", "claim", "unlock",
]


# ── HTML parser (unchanged) ───────────────────────────────────────────────────

class MarketingPageParser(HTMLParser):
    """Parse HTML and extract marketing-relevant elements."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.meta_keywords = ""
        self.og_tags = {}
        self.headings = {"h1": [], "h2": [], "h3": [], "h4": [], "h5": [], "h6": []}
        self.links = []
        self.images = []
        self.forms = []
        self.buttons = []
        self.scripts = []
        self.schema_data = []
        self.ctas = []
        self.social_links = []
        self.tracking_scripts = []

        self._current_tag = None
        self._current_attrs = {}
        self._in_title = False
        self._in_heading = None
        self._in_button = False
        self._in_a = False
        self._current_text = ""
        self._in_script = False
        self._script_type = ""
        self._in_form = False
        self._current_form = {}
        self._form_fields = []
        self._text_content = []
        self._has_viewport = False
        self._canonical = ""
        self._robots_meta = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self._current_tag = tag
        self._current_attrs = attrs_dict

        if tag == "title":
            self._in_title = True
            self._current_text = ""

        elif tag == "meta":
            name = attrs_dict.get("name", "").lower()
            prop = attrs_dict.get("property", "").lower()
            content = attrs_dict.get("content", "")
            if name == "description":
                self.meta_description = content
            elif name == "keywords":
                self.meta_keywords = content
            elif name == "viewport":
                self._has_viewport = True
            elif name == "robots":
                self._robots_meta = content
            elif prop.startswith("og:"):
                self.og_tags[prop] = content

        elif tag == "link":
            if "canonical" in attrs_dict.get("rel", ""):
                self._canonical = attrs_dict.get("href", "")

        elif tag in self.headings:
            self._in_heading = tag
            self._current_text = ""

        elif tag == "a":
            self._in_a = True
            self._current_text = ""
            href = attrs_dict.get("href", "")
            self.links.append({"href": href, "text": "", "attrs": attrs_dict})
            for platform in ["twitter.com", "x.com", "facebook.com", "linkedin.com",
                             "instagram.com", "youtube.com", "tiktok.com", "github.com"]:
                if platform in href:
                    self.social_links.append({"platform": platform.split(".")[0], "url": href})

        elif tag == "img":
            self.images.append({
                "src": attrs_dict.get("src", ""),
                "alt": attrs_dict.get("alt", ""),
                "has_alt": "alt" in attrs_dict,
                "loading": attrs_dict.get("loading", ""),
            })

        elif tag == "button":
            self._in_button = True
            self._current_text = ""

        elif tag == "form":
            self._in_form = True
            self._current_form = {
                "action": attrs_dict.get("action", ""),
                "method": attrs_dict.get("method", "GET").upper(),
            }
            self._form_fields = []

        elif tag == "input" and self._in_form:
            self._form_fields.append({
                "type": attrs_dict.get("type", "text"),
                "name": attrs_dict.get("name", ""),
                "placeholder": attrs_dict.get("placeholder", ""),
                "required": "required" in attrs_dict,
            })

        elif tag == "script":
            self._in_script = True
            self._script_type = attrs_dict.get("type", "")
            self._current_text = ""
            src = attrs_dict.get("src", "")
            if src:
                self.scripts.append(src)
                tracking_indicators = {
                    "gtag": "Google Analytics (gtag)",
                    "googletagmanager": "Google Tag Manager",
                    "google-analytics": "Google Analytics",
                    "analytics": "Analytics",
                    "fbevents": "Meta Pixel",
                    "facebook": "Meta/Facebook",
                    "snap.licdn": "LinkedIn Insight Tag",
                    "hotjar": "Hotjar",
                    "fullstory": "FullStory",
                    "mixpanel": "Mixpanel",
                    "amplitude": "Amplitude",
                    "segment": "Segment",
                    "hubspot": "HubSpot",
                    "intercom": "Intercom",
                    "crisp": "Crisp Chat",
                    "drift": "Drift",
                    "tiktok": "TikTok Pixel",
                    "clarity": "Microsoft Clarity",
                }
                src_lower = src.lower()
                for indicator, name in tracking_indicators.items():
                    if indicator in src_lower:
                        self.tracking_scripts.append(name)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
            self.title = self._current_text.strip()

        elif tag in self.headings and self._in_heading == tag:
            text = self._current_text.strip()
            if text:
                self.headings[tag].append(text)
            self._in_heading = None

        elif tag == "a" and self._in_a:
            self._in_a = False
            text = self._current_text.strip()
            if self.links:
                self.links[-1]["text"] = text
            text_lower = text.lower()
            for cta in _CTA_TEXT_WORDS:
                if cta in text_lower:
                    self.ctas.append({"text": text, "href": self.links[-1]["href"], "type": "link"})
                    break
            # Language-agnostic: links whose href points at a contact/form URL
            href_lower = (self.links[-1]["href"] or "").lower()
            for pattern in _CONTACT_HREF_PATTERNS:
                if pattern in href_lower:
                    self.ctas.append({"text": text or href_lower, "href": self.links[-1]["href"], "type": "contact_link"})
                    break

        elif tag == "button" and self._in_button:
            self._in_button = False
            text = self._current_text.strip()
            if text:
                self.buttons.append(text)
                self.ctas.append({"text": text, "type": "button"})

        elif tag == "form" and self._in_form:
            self._in_form = False
            self._current_form["fields"] = self._form_fields
            self._current_form["field_count"] = len(self._form_fields)
            self.forms.append(self._current_form)

        elif tag == "script" and self._in_script:
            self._in_script = False
            script_content = self._current_text
            if "gtag" in script_content or "dataLayer" in script_content:
                if "Google Analytics" not in self.tracking_scripts and "Google Tag Manager" not in self.tracking_scripts:
                    self.tracking_scripts.append("Google Analytics/GTM (inline)")
            if "fbq" in script_content:
                if "Meta Pixel" not in self.tracking_scripts:
                    self.tracking_scripts.append("Meta Pixel (inline)")
            if self._script_type == "application/ld+json":
                try:
                    schema = json.loads(script_content)
                    if isinstance(schema, list):
                        self.schema_data.extend(schema)
                    else:
                        self.schema_data.append(schema)
                except (json.JSONDecodeError, ValueError):
                    pass

    def handle_data(self, data):
        if self._in_title or self._in_heading or self._in_a or self._in_button or self._in_script:
            self._current_text += data
        self._text_content.append(data)

    def get_full_text(self):
        return " ".join(self._text_content)

    def get_results(self):
        images_without_alt = sum(1 for img in self.images if not img.get("has_alt") or not img.get("alt"))
        images_with_lazy = sum(1 for img in self.images if img.get("loading") == "lazy")

        heading_issues = []
        if not self.headings["h1"]:
            heading_issues.append("Missing H1 tag")
        elif len(self.headings["h1"]) > 1:
            heading_issues.append(f"Multiple H1 tags ({len(self.headings['h1'])})")
        if self.headings["h3"] and not self.headings["h2"]:
            heading_issues.append("H3 used without H2 (skipped level)")

        full_text = self.get_full_text()
        word_count = len(full_text.split())

        return {
            "seo": {
                "title": self.title,
                "title_length": len(self.title),
                "title_ok": 30 <= len(self.title) <= 60,
                "meta_description": self.meta_description,
                "meta_description_length": len(self.meta_description),
                "meta_description_ok": 120 <= len(self.meta_description) <= 160,
                "canonical": self._canonical,
                "robots_meta": self._robots_meta,
                "has_viewport": self._has_viewport,
                "og_tags": self.og_tags,
                "headings": {k: v for k, v in self.headings.items() if v},
                "heading_issues": heading_issues,
                "images_total": len(self.images),
                "images_without_alt": images_without_alt,
                "images_with_lazy_loading": images_with_lazy,
            },
            "content": {
                "word_count": word_count,
                "headings_count": sum(len(v) for v in self.headings.values()),
                "h1": self.headings["h1"],
                "h2": self.headings["h2"],
            },
            "conversion": {
                "ctas": self.ctas[:20],
                "cta_count": len(self.ctas),
                "forms": self.forms,
                "form_count": len(self.forms),
                "buttons": self.buttons[:20],
            },
            "trust": {
                "social_links": self.social_links,
                "social_link_count": len(self.social_links),
            },
            "tracking": {
                "tools_detected": list(set(self.tracking_scripts)),
                "tools_count": len(set(self.tracking_scripts)),
                "schema_types": [s.get("@type", "Unknown") for s in self.schema_data],
                "schema_count": len(self.schema_data),
            },
            "technical": {
                "total_links": len(self.links),
                "internal_links": 0,
                "external_links": 0,
                "scripts_count": len(self.scripts),
            },
        }


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5,he;q=0.3",
}


def fetch_page(url, timeout=PAGE_TIMEOUT):
    """Fetch a webpage and return its HTML content, or None on failure."""
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        response = urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx())
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and content_type:
            return None  # skip binary / non-HTML responses
        return response.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def fetch_robots_txt(url):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    content = fetch_page(robots_url)
    if content:
        return {"exists": True, "has_sitemap_reference": "sitemap:" in content.lower(), "content_preview": content[:500]}
    return {"exists": False}


def fetch_sitemap(url):
    parsed = urlparse(url)
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    try:
        req = urllib.request.Request(sitemap_url, headers={"User-Agent": "MarketingBot/1.0"})
        response = urllib.request.urlopen(req, timeout=10, context=_ssl_ctx())
        content = response.read().decode("utf-8", errors="replace")
        url_count = content.lower().count("<url>") or content.lower().count("<loc>")
        # Extract first N page URLs from the sitemap to seed the crawler
        import re as _re
        locs = _re.findall(r"<loc>(.*?)</loc>", content, _re.IGNORECASE)
        return {"exists": True, "url_count": url_count, "sample_urls": locs[:30]}
    except Exception:
        return {"exists": False, "url_count": 0, "sample_urls": []}


# ── Multi-page crawler ────────────────────────────────────────────────────────

def _normalize_url(url):
    """Strip fragment and trailing slash for deduplication."""
    p = urlparse(url)
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme, p.netloc, path, p.params, p.query, ""))


def _is_skippable(url):
    path = urlparse(url).path.lower()
    # Skip by file extension
    dot_pos = path.rfind(".")
    if dot_pos != -1 and path[dot_pos:] in _SKIP_EXT:
        return True
    # Skip by path pattern
    for pat in _SKIP_PATTERNS:
        if path.startswith(pat):
            return True
    return False


def crawl_site(start_url, max_pages=MAX_PAGES):
    """
    BFS crawl of the target domain.  Returns a list of (url, MarketingPageParser)
    tuples for every successfully fetched page, homepage first.
    """
    parsed_base = urlparse(start_url)
    domain = parsed_base.netloc

    visited = set()
    queue = [start_url]
    pages = []   # (url, parser)

    # Optionally seed from sitemap for deeper coverage
    sitemap = fetch_sitemap(start_url)
    for loc in sitemap.get("sample_urls", []):
        if urlparse(loc).netloc == domain:
            queue.append(loc)

    while queue and len(pages) < max_pages:
        url = queue.pop(0)

        norm = _normalize_url(url)
        if norm in visited:
            continue
        if _is_skippable(url):
            continue
        visited.add(norm)

        html = fetch_page(url)
        if not html:
            continue

        parser = MarketingPageParser()
        try:
            parser.feed(html)
        except Exception:
            continue

        pages.append((url, parser))

        # Enqueue internal links found on this page
        for link in parser.links:
            href = link.get("href", "") or ""
            if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            absolute = urljoin(url, href)
            abs_parsed = urlparse(absolute)
            if abs_parsed.netloc != domain:
                continue
            if abs_parsed.scheme not in ("http", "https"):
                continue
            norm_abs = _normalize_url(absolute)
            if norm_abs not in visited:
                queue.append(absolute)

    return pages


def merge_pages(start_url, pages):
    """
    Merge findings from all crawled pages into one unified result dict
    ready for scoring.  SEO metadata comes from the homepage; conversion,
    trust, and tracking signals are unioned across all pages.
    """
    if not pages:
        return {}

    home_url, home_parser = pages[0]
    home = home_parser.get_results()

    all_forms = []
    all_ctas = []
    all_buttons = []
    all_social = []
    all_tracking = []
    all_schema = []
    all_images = []
    total_words = 0
    page_urls = []

    for url, parser in pages:
        page_urls.append(url)
        r = parser.get_results()
        all_forms.extend(r["conversion"]["forms"])
        all_ctas.extend(r["conversion"]["ctas"])
        all_buttons.extend(r["conversion"]["buttons"])
        all_social.extend(r["trust"]["social_links"])
        all_tracking.extend(r["tracking"]["tools_detected"])
        all_schema.extend(parser.schema_data)
        all_images.extend(parser.images)
        total_words += r["content"]["word_count"]

    # Deduplicate social links and tracking tools
    seen = set()
    unique_social = []
    for s in all_social:
        key = s.get("platform", "") + s.get("url", "")
        if key not in seen:
            seen.add(key)
            unique_social.append(s)

    unique_tracking = list(set(all_tracking))
    schema_types = list(set(s.get("@type", "Unknown") for s in all_schema))

    # Deduplicate CTAs (same text+href from repeated nav bars)
    seen_cta = set()
    unique_ctas = []
    for c in all_ctas:
        key = (c.get("text", "")[:60], c.get("href", "")[:100])
        if key not in seen_cta:
            seen_cta.add(key)
            unique_ctas.append(c)

    images_without_alt = sum(1 for img in all_images if not img.get("has_alt") or not img.get("alt"))

    # Internal / external link counts from homepage
    domain = urlparse(start_url).netloc
    internal = sum(1 for l in home_parser.links if (l.get("href", "").startswith("/") or domain in l.get("href", "")))
    external = sum(1 for l in home_parser.links if l.get("href", "").startswith("http") and domain not in l.get("href", ""))

    return {
        # SEO metadata from homepage only (title, meta, H1, etc. are page-specific)
        "seo": {
            **home["seo"],
            "images_total": len(all_images),
            "images_without_alt": images_without_alt,
        },
        "content": {
            "word_count": total_words,
            "headings_count": sum(len(v) for v in home_parser.headings.values()),
            "h1": home_parser.headings["h1"],
            "h2": home_parser.headings["h2"],
        },
        "conversion": {
            "ctas": unique_ctas[:30],
            "cta_count": len(unique_ctas),
            "forms": all_forms,
            "form_count": len(all_forms),
            "buttons": list(set(all_buttons))[:20],
        },
        "trust": {
            "social_links": unique_social,
            "social_link_count": len(unique_social),
        },
        "tracking": {
            "tools_detected": unique_tracking,
            "tools_count": len(unique_tracking),
            "schema_types": schema_types,
            "schema_count": len(all_schema),
        },
        "technical": {
            "total_links": len(home_parser.links),
            "internal_links": internal,
            "external_links": external,
            "scripts_count": len(home_parser.scripts),
        },
        # Filled in by analyze()
        "robots": {},
        "sitemap": {},
        # Crawler metadata — visible to the LLM that writes the report
        "crawl": {
            "pages_fetched": len(pages),
            "page_urls": page_urls,
        },
    }


# ── Main analysis entry point ─────────────────────────────────────────────────

def analyze(url, max_pages=MAX_PAGES):
    """Run full multi-page marketing analysis on a domain."""
    results = {"url": url, "status": "success"}

    pages = crawl_site(url, max_pages=max_pages)

    if not pages:
        return {"url": url, "status": "error", "message": "Could not fetch page"}

    page_results = merge_pages(url, pages)
    page_results["robots"] = fetch_robots_txt(url)
    page_results["sitemap"] = fetch_sitemap(url)

    # ── Scoring (operates on merged site-wide data) ───────────────────────────
    scores = {}

    # SEO score
    seo_score = 10
    seo = page_results["seo"]
    if not seo["title"]:
        seo_score -= 3
    elif not seo["title_ok"]:
        seo_score -= 1
    if not seo["meta_description"]:
        seo_score -= 3
    elif not seo["meta_description_ok"]:
        seo_score -= 1
    if not seo["headings"].get("h1"):
        seo_score -= 2
    if seo["images_without_alt"] > 0:
        seo_score -= min(2, seo["images_without_alt"])
    if seo["heading_issues"]:
        seo_score -= 1
    if not seo["has_viewport"]:
        seo_score -= 1
    scores["seo"] = max(0, seo_score)

    # CTA / conversion score — now counts across all pages
    conv = page_results["conversion"]
    cta_score = 1 if conv["cta_count"] == 0 else 5
    if conv["cta_count"] >= 2:
        cta_score = 7
    if conv["cta_count"] >= 4:
        cta_score = 8
    if conv["form_count"] >= 1:
        cta_score = min(10, cta_score + 1)
    value_ctas = [c for c in conv["ctas"] if len(c.get("text", "")) > 10]
    if value_ctas:
        cta_score = min(10, cta_score + 1)
    scores["cta"] = cta_score

    # Trust score
    trust_score = 5
    if page_results["trust"]["social_link_count"] >= 3:
        trust_score += 2
    elif page_results["trust"]["social_link_count"] >= 1:
        trust_score += 1
    if page_results["tracking"]["schema_count"] > 0:
        trust_score += 1
    scores["trust"] = min(10, trust_score)

    # Tracking / analytics score
    track_score = 3
    if page_results["tracking"]["tools_count"] >= 3:
        track_score = 9
    elif page_results["tracking"]["tools_count"] >= 2:
        track_score = 7
    elif page_results["tracking"]["tools_count"] >= 1:
        track_score = 5
    scores["tracking"] = track_score

    page_results["scores"] = scores
    page_results["overall_score"] = round(sum(scores.values()) / len(scores), 1)

    results["analysis"] = page_results
    results["pages_crawled"] = len(pages)
    return results


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "usage": "python3 analyze_page.py <url> [max_pages]",
            "example": "python3 analyze_page.py https://example.com 15",
            "description": "Crawls up to max_pages internal pages and scores the whole site",
        }, indent=2))
        return

    url = sys.argv[1]
    if not url.startswith("http"):
        url = "https://" + url

    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else MAX_PAGES

    results = analyze(url, max_pages=max_pages)
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
