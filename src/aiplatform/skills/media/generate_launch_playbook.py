"""
Skill: generate_launch_playbook
Generate an 8-week podcast launch plan for new or relaunching shows.

Week breakdown (market-launch methodology):
  Weeks 1-2: Foundation — positioning, landing page brief, asset creation checklist
  Weeks 3-4: Audience building — content seeding, guest pre-outreach, beta listener list
  Weeks 5-6: Pre-launch — email teaser sequence, partner briefing, directory submissions
  Week 7:    Launch — day-by-day execution Mon–Sun
  Week 8:    Post-launch — listener feedback, metrics review, iteration plan

Also produces:
  - 5-email launch teaser sequence (teaser → building → early access → launch day → follow-up)
  - Platform-specific social posts for launch week
  - Guest/partner outreach timeline
  - KPIs and metrics dashboard setup

Input:
    show_context    dict    — {show_name, niche, audience, host_name, show_concept,
                               host_background, launch_type (new|relaunch)}
    max_tokens      int     — default 10000

Output:
    {
        "executive_summary":   str,
        "week_by_week":        list[dict],   # [{week, title, tasks}]
        "email_templates":     list[dict],   # [{number, subject, body}]
        "social_posts":        list[dict],   # [{platform, copy, timing}]
        "kpis":                list[str],
        "raw_playbook":        str,
        "cost_usd":            float,
    }
"""

from __future__ import annotations

import os
import re


SYSTEM_PROMPT = """\
You are a podcast launch strategist. You build practical, week-by-week launch plans
that solo hosts can execute without an agency or a big budget.

Every recommendation must be:
- Specific to THIS show's niche and audience — not generic podcast advice
- Actionable this week — not vague ("build an audience")
- Realistic for a solo creator — assume no team, no paid ads unless specified

The playbook should read like instructions from a trusted advisor, not a marketing template.
"""

_WEEK_PATTERN = re.compile(
    r"===WEEK\s*(\d+)(?:[^=]*)===(.+?)(?====WEEK|\Z)",
    re.DOTALL | re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(
    r"\[EMAIL\s+(\d+)\](.*?)\[/EMAIL\]",
    re.DOTALL | re.IGNORECASE,
)
_EMAIL_FIELD = re.compile(
    r"^(Subject|Body):\s*(.+?)(?=\n(?:Subject|Body):|$)",
    re.MULTILINE | re.DOTALL,
)
_SOCIAL_PATTERN = re.compile(
    r"\[SOCIAL:\s*([^\]]+)\](.*?)\[/SOCIAL\]",
    re.DOTALL | re.IGNORECASE,
)
_SUMMARY_PATTERN = re.compile(
    r"===EXECUTIVE_SUMMARY===(.*?)(?====|$)", re.DOTALL | re.IGNORECASE,
)
_KPIS_PATTERN = re.compile(
    r"===KPIS===(.*?)(?====|$)", re.DOTALL | re.IGNORECASE,
)


def generate_launch_playbook(
    show_context: dict,
    max_tokens: int = 10000,
) -> dict:
    """
    Generate a full 8-week podcast launch playbook.
    Requires ANTHROPIC_API_KEY.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_message = _build_prompt(show_context)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        temperature=0.3,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    parsed = _parse_playbook(raw)

    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )

    return {**parsed, "raw_playbook": raw, "cost_usd": cost_usd}


# ─── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(ctx: dict) -> str:
    show = ctx.get("show_name", "the podcast")
    niche = ctx.get("niche", "general")
    audience = ctx.get("audience", "general audience")
    host = ctx.get("host_name", "the host")
    concept = ctx.get("show_concept", "")
    background = ctx.get("host_background", "")
    launch_type = ctx.get("launch_type", "new")

    type_note = (
        "This is a RELAUNCH — the show has existed before. "
        "Account for re-engagement of lapsed listeners alongside new audience acquisition."
        if launch_type == "relaunch"
        else "This is a NEW show — building from zero."
    )

    concept_line = f"Show concept: {concept}\n" if concept else ""
    background_line = f"Host background: {background}\n" if background else ""

    return f"""\
Build a complete 8-week podcast launch playbook for the show below.

SHOW DETAILS:
Show: {show}
Niche: {niche}
Audience: {audience}
Host: {host}
{concept_line}{background_line}Launch type: {type_note}

PLAYBOOK REQUIREMENTS:

===EXECUTIVE_SUMMARY===
2-3 paragraph strategic overview: what makes this show different, who it's for,
and the one thing the launch must achieve in Week 7.

===WEEK 1-2: Foundation===
Key tasks with specific deliverables. Include:
- Positioning statement (fill-in-the-blank template for this show)
- Landing page brief (headline, subheadline, CTA, social proof placeholders)
- Asset creation checklist (cover art specs, trailer script structure, descriptions)

===WEEK 3-4: Audience Building===
Key tasks with specific deliverables. Include:
- Content seeding strategy (where to show up before launch)
- Beta listener recruitment (how many, where to find them, what to ask)
- Guest pre-outreach plan for launch episodes

===WEEK 5-6: Pre-Launch===
Key tasks with specific deliverables. Include:
- Directory submission checklist (Apple, Spotify, etc.)
- Partner/collaborator briefing template
- Launch week content calendar outline

===WEEK 7: Launch Week (Day-by-Day)===
Monday through Sunday — specific tasks per day with timing.
Include social posts, email sends, and engagement activities.

===WEEK 8: Post-Launch===
Key tasks with specific deliverables. Include:
- Listener feedback collection method
- Metrics review framework
- 30-day iteration plan

5 EMAIL LAUNCH SEQUENCE — output each in this format:
[EMAIL 1]
Subject: [subject line]
Body:
[email body]
[/EMAIL]
(Email 1: Teaser — 3 weeks before. Email 2: Building — 2 weeks before.
Email 3: Early Access — 1 week before. Email 4: Launch Day. Email 5: Follow-up — Day 3.)

SOCIAL LAUNCH POSTS — output each in this format:
[SOCIAL: LinkedIn]
[copy for LinkedIn launch post]
[/SOCIAL]
[SOCIAL: Instagram]
[copy]
[/SOCIAL]
[SOCIAL: Twitter]
[copy]
[/SOCIAL]

===KPIS===
List 8-10 specific metrics to track, with targets for Week 1, Month 1, and Month 3.
Format each as: Metric | W1 Target | M1 Target | M3 Target
"""


# ─── Parser ───────────────────────────────────────────────────────────────────

def _parse_playbook(raw: str) -> dict:
    result: dict = {
        "executive_summary": "",
        "week_by_week":      [],
        "email_templates":   [],
        "social_posts":      [],
        "kpis":              [],
    }

    # Executive summary
    sm = _SUMMARY_PATTERN.search(raw)
    if sm:
        result["executive_summary"] = sm.group(1).strip()

    # Week blocks
    for match in _WEEK_PATTERN.finditer(raw):
        week_num = match.group(1)
        body = match.group(2).strip()
        # First line is often the title
        lines = body.splitlines()
        title = lines[0].strip().lstrip("#").strip() if lines else f"Week {week_num}"
        tasks = [l.strip() for l in lines[1:] if l.strip()]
        result["week_by_week"].append({
            "week":  week_num,
            "title": title,
            "tasks": tasks,
        })

    # Email templates
    for match in _EMAIL_PATTERN.finditer(raw):
        num = int(match.group(1))
        block = match.group(2).strip()
        fields: dict[str, str] = {}
        for m in _EMAIL_FIELD.finditer(block):
            fields[m.group(1).lower()] = m.group(2).strip()
        result["email_templates"].append({
            "number":  num,
            "subject": fields.get("subject", ""),
            "body":    fields.get("body", ""),
        })

    # Social posts
    for match in _SOCIAL_PATTERN.finditer(raw):
        result["social_posts"].append({
            "platform": match.group(1).strip(),
            "copy":     match.group(2).strip(),
        })

    # KPIs
    km = _KPIS_PATTERN.search(raw)
    if km:
        result["kpis"] = [
            line.strip()
            for line in km.group(1).strip().splitlines()
            if line.strip() and not line.strip().startswith("===")
        ]

    return result
