import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from aiplatform.database.session import SessionLocal
from aiplatform.database.models import AdvisoryProposal
from aiplatform.skills.finance.log_cost import log_cost

log = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent.parent.parent / "registry" / "advisors.json"
PROMPTS_DIR = REGISTRY_PATH.parent / "prompts"

# Pricing approximation for cost logging (claude-sonnet-4-6 ~$3/M input, $15/M output)
_APPROX_COST_PER_CALL = 0.008


def load_advisors_registry() -> dict:
    with open(REGISTRY_PATH, "r") as f:
        return json.load(f)


def _load_system_prompt(prompt_ref: str) -> str:
    prompt_file = PROMPTS_DIR / f"{prompt_ref}.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    log.warning("Prompt file not found: %s", prompt_file)
    return "You are a strategic business advisor. Analyse the provided context and give a concise, actionable recommendation."


def _build_user_message(advisor_id: str, context_data: dict) -> str:
    context_json = json.dumps(context_data, indent=2, default=str)
    return (
        f"Context data for your analysis:\n\n```json\n{context_json}\n```\n\n"
        "Respond with a JSON object in this exact format:\n"
        "{\n"
        '  "category": "<short category label, e.g. Tech Debt / Revenue Opportunity / Efficiency>",\n'
        '  "summary": "<one-sentence headline of the insight>",\n'
        '  "recommendation": "<detailed actionable recommendation, 2–5 sentences>",\n'
        '  "priority": <integer 1-5, where 1=critical and 5=low>\n'
        "}\n\n"
        "Return only the JSON object — no markdown fences, no extra text."
    )


def run_advisor(advisor_id: str, context_data: dict, job_id: str = None) -> dict:
    """
    Run a specific advisor persona against the provided context data,
    generate a proposal via Claude, log costs, and save to DB.
    """
    registry = load_advisors_registry()
    if advisor_id not in registry:
        raise ValueError(f"Unknown advisor_id: {advisor_id}")

    config = registry[advisor_id]
    prompt_ref = config.get("prompt_ref", f"{advisor_id}_v1")
    system_prompt = _load_system_prompt(prompt_ref)

    log.info("Running advisor '%s' (prompt_ref=%s)", advisor_id, prompt_ref)

    # ── Real LLM call via Anthropic API ───────────────────────────────────────
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    user_message = _build_user_message(advisor_id, context_data)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = message.content[0].text.strip()
    log.debug("Advisor '%s' raw response: %s", advisor_id, raw_text[:500])

    # Parse JSON response
    try:
        parsed = json.loads(raw_text)
        category = str(parsed.get("category", "General Advice"))[:255]
        summary = str(parsed.get("summary", ""))
        recommendation = str(parsed.get("recommendation", ""))
        priority = int(parsed.get("priority", 3))
        priority = max(1, min(5, priority))  # clamp to 1–5
        content = {
            "summary": summary,
            "recommendation": recommendation,
            "raw_context": context_data,
        }
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        log.warning("Could not parse advisor JSON response (%s) — storing raw text", exc)
        category = "General Advice"
        content = {"raw_response": raw_text, "raw_context": context_data}
        priority = 3

    # ── Log cost ──────────────────────────────────────────────────────────────
    log_cost(
        tool_id="claude-sonnet-4-6",
        capability="strategy",
        cost_usd=_APPROX_COST_PER_CALL,
        job_id=job_id,
        venture="platform",
    )

    # ── Persist proposal ──────────────────────────────────────────────────────
    with SessionLocal() as db:
        proposal = AdvisoryProposal(
            advisor_id=advisor_id,
            category=category,
            content=content,
            status="pending_review",
            priority=priority,
            job_id=job_id,
        )
        db.add(proposal)
        db.commit()
        db.refresh(proposal)

        log.info(
            "Advisor '%s' proposal saved — id=%s priority=%s category='%s'",
            advisor_id, proposal.id, priority, category,
        )

        return {
            "id": str(proposal.id),
            "advisor_id": proposal.advisor_id,
            "category": category,
            "priority": priority,
            "status": proposal.status,
        }
