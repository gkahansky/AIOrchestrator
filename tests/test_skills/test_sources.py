"""Unit tests for the lead-search source handlers, filters, provider slot,
and the Apify runner (caching + cost cap)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from aiplatform.skills.research.sources import (
    apify, _cache, _provider, linkedin, facebook, instagram,
)
from aiplatform.skills.research.sources.base import RawPost
from aiplatform.skills.research.sources._filters import apply_filters
from aiplatform.skills.research.sources.query_builder import (
    Filters, boolean_query, filters_from_config,
)


# ── query builder + filters ──────────────────────────────────────────────────

def test_boolean_query_quotes_phrases():
    assert boolean_query(["seo help", "audit"]) == '"seo help" OR audit'


def test_filters_from_config_parses_knobs():
    f = filters_from_config({"recency_days": "30", "min_engagement": "5", "max_results": "10"})
    assert (f.recency_days, f.min_engagement, f.max_results) == (30, 5, 10)


def test_apply_filters_drops_stale_and_low_engagement_keeps_unknown():
    posts = [
        RawPost(text="a" * 40, posted_at="2020-01-01T00:00:00Z", engagement=100),  # stale
        RawPost(text="b" * 40),                                                     # unknown -> keep
        RawPost(text="c" * 40, posted_at="2099-01-01T00:00:00Z", engagement=1),     # below min
    ]
    kept = apply_filters(posts, Filters(recency_days=30, min_engagement=5))
    assert len(kept) == 1
    assert kept[0].text.startswith("b")


# ── LinkedIn / Facebook now capture profile identity ─────────────────────────

def test_linkedin_apify_captures_author_identity(monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "x")
    monkeypatch.setattr(apify, "run_actor", lambda *a, **k: [{
        "text": "Need an SEO expert, my site is not converting at all this quarter.",
        "authorName": "Jane Smith",
        "url": "https://www.linkedin.com/posts/abc",
        "authorProfileUrl": "https://www.linkedin.com/in/jane-smith-123/",
        "authorHeadline": "Founder at Acme",
        "postedAtISO": "2099-01-01T00:00:00Z",
        "numLikes": 10, "numComments": 3,
    }])
    posts = linkedin.search(["seo help"], {})
    assert len(posts) == 1
    p = posts[0]
    assert p.author_url == "https://www.linkedin.com/in/jane-smith-123/"
    assert p.author_handle == "jane-smith-123"
    assert p.engagement == 13
    assert p.author_headline == "Founder at Acme"


def test_facebook_apify_captures_author_identity(monkeypatch):
    monkeypatch.setenv("APIFY_API_TOKEN", "x")
    monkeypatch.setattr(apify, "run_actor", lambda *a, **k: [{
        "text": "Struggling to keep my small business website accessible and compliant.",
        "authorName": "Bob Lee",
        "url": "https://www.facebook.com/groups/smallbiz/posts/1",
        "user": {"profileUrl": "https://www.facebook.com/bob.lee", "id": "555"},
        "likesCount": 4, "commentsCount": 2,
    }])
    posts = facebook.search(["accessibility"], {"group_urls": ["https://www.facebook.com/groups/smallbiz"]})
    assert len(posts) == 1
    p = posts[0]
    assert p.author_url == "https://www.facebook.com/bob.lee"
    assert p.author_handle == "555"
    assert p.engagement == 6


def test_facebook_discovers_groups_when_none_configured(monkeypatch):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)  # force Google path
    seen = {}

    def fake_serpapi(query, num=5):
        seen["query"] = query
        return [RawPost(text="post" * 10, url="https://www.facebook.com/groups/acme/posts/9",
                        source_channel="google")]
    monkeypatch.setattr(facebook, "serpapi_search", fake_serpapi)
    posts = facebook.search(["accessibility"], {})
    # discovery ran (site:facebook.com/groups) and produced a facebook lead
    assert any("facebook.com/groups" in q for q in [seen.get("query", "")])
    assert posts and posts[0].source_channel == "facebook"


# ── provider slot ────────────────────────────────────────────────────────────

def test_provider_slot_delegates_then_falls_back(monkeypatch):
    class FakeProvider:
        def search(self, kw, cfg):
            return [RawPost(text="from-provider")]

    monkeypatch.setattr(_provider, "resolve_provider", lambda platform, config: FakeProvider())
    out = _provider.run(["x"], {}, "linkedin", lambda kw, cfg: [RawPost(text="default")])
    assert out[0].text == "from-provider"

    monkeypatch.setattr(_provider, "resolve_provider", lambda platform, config: None)
    out = _provider.run(["x"], {}, "linkedin", lambda kw, cfg: [RawPost(text="default")])
    assert out[0].text == "default"


def test_provider_error_falls_back(monkeypatch):
    class Boom:
        def search(self, kw, cfg):
            raise RuntimeError("down")

    monkeypatch.setattr(_provider, "resolve_provider", lambda platform, config: Boom())
    out = _provider.run(["x"], {}, "linkedin", lambda kw, cfg: [RawPost(text="default")])
    assert out[0].text == "default"


# ── Apify runner: caching + cost cap ─────────────────────────────────────────

class _Resp:
    status_code = 200

    def __init__(self, data):
        self._d = data

    def json(self):
        return self._d


def test_apify_caches_identical_runs(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("APIFY_API_TOKEN", "x")
    monkeypatch.setenv("APIFY_MAX_RUNS_PER_DAY", "1000")
    _cache._mem_kv.clear(); _cache._mem_ctr.clear()

    calls = {"n": 0}

    def fake_post(url, params=None, json=None, timeout=None):
        calls["n"] += 1
        return _Resp([{"text": "hello"}])
    monkeypatch.setattr(apify.requests, "post", fake_post)

    a = apify.run_actor("actor/x", {"q": 1})
    b = apify.run_actor("actor/x", {"q": 1})
    assert calls["n"] == 1            # second call served from cache
    assert a == b == [{"text": "hello"}]


def test_apify_cost_cap_returns_empty(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("APIFY_API_TOKEN", "x")
    monkeypatch.setenv("APIFY_MAX_RUNS_PER_DAY", "1")
    _cache._mem_kv.clear(); _cache._mem_ctr.clear()

    calls = {"n": 0}

    def fake_post(url, params=None, json=None, timeout=None):
        calls["n"] += 1
        return _Resp([{"text": "ok"}])
    monkeypatch.setattr(apify.requests, "post", fake_post)

    first = apify.run_actor("actor/y", {"q": 1})
    second = apify.run_actor("actor/z", {"q": 2})   # distinct input -> not cached, over cap
    assert len(first) == 1
    assert second == []
    assert calls["n"] == 1


def test_apify_no_token_is_noop(monkeypatch):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    assert apify.run_actor("actor/x", {"q": 1}) == []
