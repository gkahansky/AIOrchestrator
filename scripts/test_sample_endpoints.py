"""
Test script for public sample endpoints.

Usage:
    python scripts/test_sample_endpoints.py                        # audit only (no audio file needed)
    python scripts/test_sample_endpoints.py --podcast path/to.mp3 # both endpoints
    python scripts/test_sample_endpoints.py --local                # hit localhost:8000 instead

Options:
    --email    EMAIL       Recipient for sample delivery (default: test@example.com)
    --url      URL         Website to audit (default: https://echoforge.biz)
    --podcast  FILE        Audio file to upload for podcast test
    --local                Use http://localhost:8000 instead of production
    --check-openapi        Just print all routes from /openapi.json and exit
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

PROD_BASE  = "https://api.planBadmin.com"
LOCAL_BASE = "http://localhost:8000"


def _print(label: str, ok: bool, detail: str = "") -> None:
    icon = "✅" if ok else "❌"
    print(f"  {icon}  {label}")
    if detail:
        print(f"       {detail}")


def check_openapi(base: str) -> None:
    print(f"\n── OpenAPI routes ({base}) ──────────────────────────────")
    try:
        r = requests.get(f"{base}/openapi.json", timeout=10)
        r.raise_for_status()
        paths = r.json().get("paths", {})
        sample_paths = [p for p in paths if "/sample" in p]
        if sample_paths:
            for p in sample_paths:
                methods = list(paths[p].keys())
                print(f"  {', '.join(m.upper() for m in methods)}  {p}")
        else:
            print("  ⚠️  No /sample routes found in OpenAPI spec")
            print(f"  All routes: {list(paths.keys())[:10]} ...")
    except Exception as e:
        print(f"  ❌ Failed to fetch OpenAPI spec: {e}")


def test_health(base: str) -> bool:
    print(f"\n── Health check ─────────────────────────────────────────")
    try:
        r = requests.get(f"{base}/api/health", timeout=10)
        ok = r.status_code == 200
        _print(f"GET /api/health → {r.status_code}", ok, r.text[:120])
        return ok
    except Exception as e:
        _print("GET /api/health", False, str(e))
        return False


def test_audit(base: str, email: str, url: str) -> bool:
    print(f"\n── POST /api/sample/audit ───────────────────────────────")
    print(f"  URL:   {url}")
    print(f"  Email: {email}")

    try:
        r = requests.post(
            f"{base}/api/sample/audit",
            data={"url": url, "email": email},
            timeout=30,
        )
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        ok = r.status_code in (200, 202)
        _print(f"Response {r.status_code}", ok, json.dumps(data, indent=2)[:300])

        if r.status_code == 422:
            print(f"  ⚠️  Validation error detail: {r.text[:400]}")
        if r.status_code == 429:
            print(f"  ⚠️  Rate limited — already submitted for this email in last 24h")
        return ok

    except Exception as e:
        _print("Request failed", False, str(e))
        return False


def test_audit_validation(base: str) -> None:
    """Test that bad input is rejected."""
    print(f"\n── Audit validation (expect 422) ────────────────────────")
    r = requests.post(f"{base}/api/sample/audit", data={"url": "not-a-url", "email": "bad"}, timeout=10)
    ok = r.status_code == 422
    _print(f"Bad input → {r.status_code} (expect 422)", ok)


def test_podcast(base: str, email: str, audio_path: str) -> bool:
    print(f"\n── POST /api/sample/podcast ─────────────────────────────")
    path = Path(audio_path)
    if not path.exists():
        _print(f"Audio file not found: {audio_path}", False)
        return False

    size_mb = path.stat().st_size / 1024 / 1024
    print(f"  File:  {path.name} ({size_mb:.1f} MB)")
    print(f"  Email: {email}")

    try:
        with open(path, "rb") as f:
            r = requests.post(
                f"{base}/api/sample/podcast",
                data={
                    "email":         email,
                    "show_name":     "Test Show",
                    "episode_title": "Test Episode — Endpoint Validation",
                    "host_name":     "Test Host",
                },
                files={"audio": (path.name, f, "audio/mpeg")},
                timeout=120,
            )
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        ok = r.status_code in (200, 202)
        _print(f"Response {r.status_code}", ok, json.dumps(data, indent=2)[:300])

        if r.status_code == 413:
            print(f"  ⚠️  File too large (>200 MB)")
        if r.status_code == 422:
            print(f"  ⚠️  Validation error: {r.text[:400]}")
        if r.status_code == 429:
            print(f"  ⚠️  Rate limited — already submitted for this email in last 24h")
        return ok

    except Exception as e:
        _print("Request failed", False, str(e))
        return False


def test_podcast_bad_format(base: str, email: str) -> None:
    """Test that unsupported file formats are rejected."""
    print(f"\n── Podcast validation (expect 422 for bad format) ───────")
    import io
    r = requests.post(
        f"{base}/api/sample/podcast",
        data={"email": email},
        files={"audio": ("test.pdf", io.BytesIO(b"fake pdf"), "application/pdf")},
        timeout=10,
    )
    ok = r.status_code == 422
    _print(f"Bad format (pdf) → {r.status_code} (expect 422)", ok)


def main():
    parser = argparse.ArgumentParser(description="Test /api/sample endpoints")
    parser.add_argument("--email",        default="test@example.com")
    parser.add_argument("--url",          default="https://echoforge.biz")
    parser.add_argument("--podcast",      default=None,  metavar="FILE")
    parser.add_argument("--local",        action="store_true")
    parser.add_argument("--check-openapi",action="store_true")
    args = parser.parse_args()

    base = LOCAL_BASE if args.local else PROD_BASE
    print(f"\nTarget: {base}")
    print(f"Email:  {args.email}")

    if args.check_openapi:
        check_openapi(base)
        sys.exit(0)

    check_openapi(base)

    healthy = test_health(base)
    if not healthy:
        print("\n⚠️  Health check failed — deployment may still be in progress. Try again in 30s.")
        sys.exit(1)

    results = []

    results.append(test_audit(base, args.email, args.url))
    test_audit_validation(base)

    if args.podcast:
        results.append(test_podcast(base, args.email, args.podcast))
        test_podcast_bad_format(base, args.email)
    else:
        print(f"\n── Podcast test skipped (pass --podcast path/to/file.mp3) ──")

    passed = sum(results)
    total  = len(results)
    print(f"\n{'─' * 55}")
    print(f"  {'✅' if passed == total else '❌'}  {passed}/{total} tests passed")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
