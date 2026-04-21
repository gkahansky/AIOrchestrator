"""
Multi-LLM research skill.

Runs the same research prompt concurrently across multiple LLM providers and
returns each model's response keyed by provider ID.

Supported providers (activated by presence of the relevant env var):
  claude  — Anthropic SDK   (ANTHROPIC_API_KEY)
  openai  — OpenAI SDK      (OPENAI_API_KEY)
  gemini  — Google GenAI    (GOOGLE_AI_API_KEY)
  grok    — xAI via OpenAI-compatible client (XAI_API_KEY)
"""

import asyncio
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Model IDs ──────────────────────────────────────────────────────────────────

_MODELS: dict[str, str] = {
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "gemini": "gemini-2.0-flash",
    "grok":   "grok-3-mini",
}

_XAI_BASE_URL = "https://api.x.ai/v1"


# ── Per-provider async callers ─────────────────────────────────────────────────

async def _call_claude(prompt: str, system: str, timeout: int, max_tokens: int = 4096) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = await asyncio.wait_for(
        client.messages.create(
            model=_MODELS["claude"],
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ),
        timeout=timeout,
    )
    return msg.content[0].text


async def _call_openai(prompt: str, system: str, timeout: int, max_tokens: int = 4096) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=_MODELS["openai"],
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        ),
        timeout=timeout,
    )
    return resp.choices[0].message.content


async def _call_gemini(prompt: str, system: str, timeout: int, max_tokens: int = 4096) -> str:
    from google import genai
    from google.genai import types as genai_types
    client = genai.Client(api_key=os.environ["GOOGLE_AI_API_KEY"])
    full_prompt = f"{system}\n\n{prompt}"
    _max = max_tokens
    resp = await asyncio.wait_for(
        asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=_MODELS["gemini"],
                contents=full_prompt,
                config=genai_types.GenerateContentConfig(max_output_tokens=_max),
            ),
        ),
        timeout=timeout,
    )
    return resp.text


async def _call_grok(prompt: str, system: str, timeout: int, max_tokens: int = 4096) -> str:
    from openai import AsyncOpenAI
    api_key = next((os.environ[k] for k in ["XAI_API_KEY", "GROK_API_KEY", "X_AI_API_KEY"] if os.environ.get(k)), None)
    if not api_key:
        raise RuntimeError("No xAI API key found (tried XAI_API_KEY, GROK_API_KEY, X_AI_API_KEY)")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=_XAI_BASE_URL,
    )
    resp = await asyncio.wait_for(
        client.chat.completions.create(
            model=_MODELS["grok"],
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        ),
        timeout=timeout,
    )
    return resp.choices[0].message.content


_CALLERS = {
    "claude": (_call_claude, "ANTHROPIC_API_KEY"),
    "openai": (_call_openai, "OPENAI_API_KEY"),
    "gemini": (_call_gemini, "GOOGLE_AI_API_KEY"),
    "grok":   (_call_grok,   "XAI_API_KEY"),
}

# xAI key may be set under any of these names on Railway
_GROK_KEY_ALIASES = ["XAI_API_KEY", "GROK_API_KEY", "X_AI_API_KEY"]


def _grok_api_key() -> str | None:
    for name in _GROK_KEY_ALIASES:
        val = os.environ.get(name)
        if val:
            return val
    return None


def available_llms() -> list[str]:
    """Return LLM IDs whose API key is present in the environment."""
    result = [llm for llm, (_, key) in _CALLERS.items() if os.environ.get(key)]
    # Add grok if found under any alias and not already present
    if "grok" not in result and _grok_api_key():
        result.append("grok")
    return result


async def _safe_call(llm_id: str, prompt: str, system: str, timeout: int, max_tokens: int = 4096) -> tuple[str, str | None, str | None]:
    """Call one LLM. Returns (llm_id, result_text | None, error | None)."""
    caller, _ = _CALLERS[llm_id]
    try:
        text = await caller(prompt, system, timeout, max_tokens)
        logger.info("multi_llm_research: %s completed (%d chars)", llm_id, len(text))
        return llm_id, text, None
    except Exception as exc:
        logger.error("multi_llm_research: %s failed — %s", llm_id, exc)
        return llm_id, None, str(exc)


async def run_parallel_research(
    prompts: dict[str, str],          # {llm_id: research_prompt}
    system_prompt: str,
    selected_llms: list[str] | None = None,
    timeout: int = 120,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """
    Run each LLM concurrently with its tailored research prompt.

    Args:
        prompts:       Per-LLM research prompts (from prompt optimizer).
                       If an LLM is selected but has no tailored prompt, the
                       first available prompt is used as fallback.
        system_prompt: Shared system context for all LLMs.
        selected_llms: Which LLMs to run. Defaults to all available.
        timeout:       Per-LLM timeout in seconds.

    Returns:
        {
            "results":  {llm_id: text},
            "errors":   {llm_id: error_string},
            "skipped":  [llm_id, ...],  # API key absent
        }
    """
    if selected_llms is None:
        selected_llms = list(prompts.keys())

    avail = set(available_llms())
    to_run   = [llm for llm in selected_llms if llm in avail]
    skipped  = [llm for llm in selected_llms if llm not in avail]

    if skipped:
        logger.warning("multi_llm_research: skipping %s — API keys absent", skipped)

    fallback_prompt = next(iter(prompts.values())) if prompts else ""

    tasks = [
        _safe_call(llm, prompts.get(llm, fallback_prompt), system_prompt, timeout, max_tokens)
        for llm in to_run
    ]
    outcomes = await asyncio.gather(*tasks)

    results: dict[str, str] = {}
    errors:  dict[str, str] = {}
    for llm_id, text, err in outcomes:
        if text is not None:
            results[llm_id] = text
        else:
            errors[llm_id] = err or "unknown error"

    return {"results": results, "errors": errors, "skipped": skipped}


def run_parallel_research_sync(
    prompts: dict[str, str],
    system_prompt: str,
    selected_llms: list[str] | None = None,
    timeout: int = 120,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Synchronous wrapper — for use inside Celery tasks."""
    return asyncio.run(
        run_parallel_research(prompts, system_prompt, selected_llms, timeout, max_tokens)
    )
