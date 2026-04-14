"""
Platform settings router.

  GET  /api/platform/settings/keys/{service}          — return masked key + test status
  PUT  /api/platform/settings/keys/{service}          — update an API key (stored in DB)
  POST /api/platform/settings/keys/{service}/test     — run a live connectivity test
  PUT  /api/platform/settings/tools/{capability}/{tool_id} — toggle a tool active/inactive

API keys are stored in a simple `platform_settings` key-value table via the
`_get_setting` / `_set_setting` helpers so secrets are never in git.  The DB
row stores the raw key; the API response always returns only the last 6 chars.

Tool-router overrides are stored in the same table as JSON so the Tool Router
can read them at runtime without a redeploy.
"""

import json
import os

from fastapi import APIRouter, Depends, HTTPException, status

from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth
from aiplatform.webapp.schemas import (
    SettingsKeyResponse,
    SettingsKeysListResponse,
    SettingsKeyTestResponse,
    SettingsKeyUpdate,
    ToolSettingResponse,
    ToolSettingUpdate,
)

router = APIRouter()

# Services whose keys we manage
_KNOWN_SERVICES = {
    "anthropic", "openai", "google_ai", "serpapi", "etsy",
    "gmail", "slack", "pinterest", "buffer", "jira", "langsmith",
}


# ── simple DB-backed KV store for settings ────────────────────────────────────

def _setting_key(service: str) -> str:
    return f"apikey:{service}"


def _get_setting(db, key: str) -> str | None:
    """Read a platform setting value from the DB."""
    try:
        from sqlalchemy import text
        row = db.execute(
            text("SELECT value FROM platform_settings WHERE key = :k"),
            {"k": key},
        ).fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _set_setting(db, key: str, value: str) -> None:
    """Upsert a platform setting value into the DB (PostgreSQL + SQLite safe)."""
    from sqlalchemy import text
    from aiplatform.database.session import DATABASE_URL

    if DATABASE_URL.startswith("sqlite"):
        # SQLite uses INSERT OR REPLACE
        db.execute(
            text(
                "INSERT OR REPLACE INTO platform_settings (key, value, updated_at) "
                "VALUES (:k, :v, datetime('now'))"
            ),
            {"k": key, "v": value},
        )
    else:
        db.execute(
            text(
                "INSERT INTO platform_settings (key, value, updated_at) "
                "VALUES (:k, :v, now()) "
                "ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = now()"
            ),
            {"k": key, "v": value},
        )
    db.commit()


def _mask(key: str) -> str:
    if not key:
        return ""
    return f"...{key[-6:]}" if len(key) > 6 else "***"


# ── /settings/keys ───────────────────────────────────────────────────────────

@router.get("/keys", response_model=SettingsKeysListResponse)
def list_api_keys(
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> SettingsKeysListResponse:
    """Return masked status for all known API key services."""
    keys = []
    for service in sorted(_KNOWN_SERVICES):
        raw = _get_setting(db, _setting_key(service)) or os.environ.get(
            f"{service.upper()}_API_KEY", ""
        )
        keys.append(SettingsKeyResponse(
            service=service,
            masked_key=_mask(raw),
            is_set=bool(raw),
        ))
    return SettingsKeysListResponse(keys=keys)


# ── /settings/keys/{service} ─────────────────────────────────────────────────

@router.get("/keys/{service}", response_model=SettingsKeyResponse)
def get_api_key(
    service: str,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> SettingsKeyResponse:
    if service not in _KNOWN_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown service '{service}'. Known: {sorted(_KNOWN_SERVICES)}",
        )
    raw = _get_setting(db, _setting_key(service)) or os.environ.get(
        f"{service.upper()}_API_KEY", ""
    )
    return SettingsKeyResponse(
        service=service,
        masked_key=_mask(raw),
        is_set=bool(raw),
    )


@router.put("/keys/{service}", response_model=SettingsKeyResponse)
def update_api_key(
    service: str,
    req: SettingsKeyUpdate,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> SettingsKeyResponse:
    if service not in _KNOWN_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown service '{service}'.",
        )
    _set_setting(db, _setting_key(service), req.key)
    return SettingsKeyResponse(
        service=service,
        masked_key=_mask(req.key),
        is_set=True,
    )


@router.post("/keys/{service}/test", response_model=SettingsKeyTestResponse)
def test_api_key(
    service: str,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> SettingsKeyTestResponse:
    if service not in _KNOWN_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown service '{service}'.",
        )

    raw = _get_setting(db, _setting_key(service)) or os.environ.get(
        f"{service.upper()}_API_KEY", ""
    )
    if not raw:
        return SettingsKeyTestResponse(service=service, ok=False, detail="Key not set")

    ok, detail = _run_connectivity_test(service, raw)
    return SettingsKeyTestResponse(service=service, ok=ok, detail=detail)


def _run_connectivity_test(service: str, key: str) -> tuple[bool, str]:
    """Lightweight live connectivity test per service."""
    try:
        if service == "anthropic":
            import anthropic
            c = anthropic.Anthropic(api_key=key)
            c.models.list()
            return True, "Connected"

        if service == "serpapi":
            import httpx
            r = httpx.get(
                "https://serpapi.com/account",
                params={"api_key": key},
                timeout=10,
            )
            if r.status_code == 200:
                return True, "Connected"
            return False, f"HTTP {r.status_code}"

        if service == "slack":
            import httpx
            r = httpx.post(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {key}"},
                timeout=10,
            )
            data = r.json()
            if data.get("ok"):
                return True, f"Connected as {data.get('user', '?')}"
            return False, data.get("error", "unknown")

        # Default: return key-is-set as a placeholder for services
        # without a free ping endpoint (Etsy sandbox, Gmail, etc.)
        return True, "Key set — live test not available for this service"

    except Exception as exc:
        return False, str(exc)


# ── /settings/tools/{capability}/{tool_id} ───────────────────────────────────

@router.put("/tools/{capability}/{tool_id}", response_model=ToolSettingResponse)
def update_tool_active(
    capability: str,
    tool_id: str,
    req: ToolSettingUpdate,
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> ToolSettingResponse:
    """
    Toggle a tool active/inactive in the Tool Router.

    Loads skills.json, updates the matching tool entry, persists the override
    to `platform_settings` (key = "tool_router_overrides"), and returns the
    updated tool config.  The Tool Router reads this key at runtime so the
    change takes effect without a redeploy.
    """
    from pathlib import Path

    registry_path = Path(__file__).parents[5] / "platform" / "registry" / "skills.json"
    try:
        skills = json.loads(registry_path.read_text())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not read skills.json: {exc}",
        )

    cap = skills.get(capability)
    if not cap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Capability '{capability}' not found in skills.json",
        )

    tool = next((t for t in cap.get("tools", []) if t["id"] == tool_id), None)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_id}' not found under capability '{capability}'",
        )

    # Persist override to DB so Tool Router picks it up at runtime
    overrides_raw = _get_setting(db, "tool_router_overrides") or "{}"
    overrides: dict = json.loads(overrides_raw)
    overrides.setdefault(capability, {})[tool_id] = {"active": req.active}
    _set_setting(db, "tool_router_overrides", json.dumps(overrides))

    return ToolSettingResponse(
        capability=capability,
        tool_id=tool_id,
        tier=tool.get("tier", "standard"),
        cost_per_call=float(tool.get("cost_per_call", 0)),
        active=req.active,
        note=tool.get("note"),
    )
