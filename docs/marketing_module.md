# Marketing Module

## Overview

The Marketing module is the cold outreach and CRM layer of the AI-Infra platform. It handles lead discovery, email composition, A/B testing, send tracking, and contact lifecycle management across all EchoForge ventures.

Accessible in the admin at **planBadmin.com/marketing**.

---

## Ventures Supported

| Venture | Service | Default Free Offer |
|---|---|---|
| `marketing_audit` | Website marketing audit | Free instant website score |
| `content_studio` | Podcast show notes | Free sample from a 10-min clip |
| `accessibility_audit` | WCAG accessibility audit | Free automated scan report |

---

## Campaign Workflow

```
Create Campaign → Generate Search Prompt (AI) → Review / Edit Prompt
    → Find Leads (Celery, background) → Review Leads
    → Generate Emails (A/B/C variants, Claude Sonnet) → Review Templates
    → Approve Templates → Send Approved → Track Opens / Replies
    → Run A/B Analysis → Iterate
```

### 1. Create Campaign

- Give the campaign a name and a **detailed goal**.
- The goal is injected into both the lead search criteria prompt and the email composition prompt.
- Write the goal in plain English describing: who you're targeting, what action you want them to take, and any specific context (e.g. "targeting SaaS founders whose landing pages have weak CTAs, goal is to get them to try the free audit").

### 2. Find Leads

Clicking **Find Leads** triggers a two-step flow:

1. Claude (Haiku) generates a structured search criteria prompt based on the campaign goal and venture.
2. A modal shows the prompt. You can edit it freely before confirming.
3. The edited prompt is passed as `search_prompt` to the Celery task, which uses it to qualify leads.

**Channels searched:**
- Reddit (public JSON API, no key required) — subreddits and keywords per venture
- Web (SerpAPI — requires `SERPAPI_KEY` env var)
- Listen Notes (podcast discovery — requires `LISTENNOTES_API_KEY` for `content_studio`)

### 3. Review Leads

The lead table shows: Name, Email, Channel, Source URL (clickable), Company / Website, Notes, Status.

Leads are deduplicated by source URL within the campaign.

### 4. Generate Emails

Claude Sonnet generates three variants (A, B, C) with distinct tones:

| Variant | Tone | Best For |
|---|---|---|
| A | Direct and specific | Leads with a named pain point |
| B | Peer-to-peer, casual | Content creators, podcasters, Reddit users |
| C | Value-first, no pitch | Startup founders, agencies |

The model is context-aware — it reads the lead's notes and channel to adapt the variant. Grammar rules are strictly enforced: proper capitalisation, no sentence fragments, no clichés, no marketing buzzwords.

Every email body includes an `{{UNSUBSCRIBE_URL}}` placeholder that is replaced with a real tracking URL at send time.

### 5. Approve Templates

Templates must be manually approved before sending. Review the subject, body, and tone notes. Edit inline if needed. Reject variants you don't want sent.

### 6. Send

Only approved templates are sent. Leads are distributed across variants (not random — the system uses the lead's context to pick the best-fitting variant tone as guidance during composition).

Before each send, the spam guard runs (see below).

After sending, each Contact record is upserted in the CRM.

### 7. Track & Analyse

- **Opens**: tracked via 1×1 GIF pixel embedded in every HTML email.
- **Replies**: tracked via webhook (`POST /api/outreach/track/reply/{send_id}`).
- **Unsubscribes**: tracked via a link in every email footer (`GET /api/outreach/unsubscribe/{send_id}`).

Click **Run Analysis** on the A/B Results tab to get Claude's interpretation and recommendations.

---

## Rules and Guardrails

### Cross-Venture Spam Guard

Before sending to any lead, the system checks the **Contacts** table by email address:

1. **Unsubscribed contacts**: never contacted again, across any campaign or venture.
2. **Cooldown**: a contact that was emailed from any campaign within the last **30 days** is skipped — even from a different venture.

### Unsubscribe

Every outreach email contains an unsubscribe link in the footer:
```
https://api.planbadmin.com/api/outreach/unsubscribe/{send_id}
```

Clicking the link:
- Marks the `OutreachSend` record as `unsubscribed`
- Upserts the `Contact` with `status = unsubscribed` and sets `unsubscribed_at`
- Updates the `Lead` status to `unsubscribed`
- Returns a confirmation HTML page

**Never override an unsubscribed contact.** This status is permanent unless the contact actively re-subscribes (mechanism TBD).

---

## Contact CRM

All contacts are stored in the `contacts` table — a unified list across all ventures.

### Contact statuses

| Status | Meaning |
|---|---|
| `approached` | We sent at least one email |
| `inquired` | They responded or filled in a form |
| `purchased` | They paid for a service |
| `unsubscribed` | They clicked unsubscribe |

### Retention

| Status | Retention |
|---|---|
| `approached`, `inquired` | 12 months from `last_activity_at`, then remove |
| `purchased` | Keep forever |
| `unsubscribed` | Keep forever (to prevent re-contacting) |

> Retention enforcement is not yet automated. A scheduled task should be added to clean up stale contacts.

### Contact enrichment

Contacts are created with whatever data we have at outreach time (name, company, website). Fields like phone and address are nullable and will be populated if enriched later via other flows (e.g. order placement, form submission).

New orders through the admin or other intake flows should upsert the Contact record to keep it current.

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API (Haiku for qualification/analysis, Sonnet for email composition) |
| `SERPAPI_KEY` | Web search for leads |
| `LISTENNOTES_API_KEY` | Podcast discovery (content_studio) |
| `RESEND_API_KEY` | Email sending via Resend |
| `EMAIL_FROM` | Verified sender address |
| `OUTREACH_SENDER_NAME` | Name shown in email sign-off (default: Gal) |
| `RAILWAY_PUBLIC_URL` | Used to build tracking pixel and unsubscribe URLs |

---

## API Reference

| Method | Path | Description |
|---|---|---|
| GET | `/api/outreach/campaigns` | List campaigns (filter by venture) |
| POST | `/api/outreach/campaigns` | Create campaign |
| GET | `/api/outreach/campaigns/{id}` | Get campaign with templates |
| PATCH | `/api/outreach/campaigns/{id}` | Update campaign |
| DELETE | `/api/outreach/campaigns/{id}` | Delete campaign (cascades) |
| POST | `/api/outreach/campaigns/{id}/generate-prompt` | AI-generate search criteria |
| POST | `/api/outreach/campaigns/{id}/find-leads` | Trigger lead search (Celery) |
| POST | `/api/outreach/campaigns/{id}/compose` | Generate A/B/C email templates |
| POST | `/api/outreach/campaigns/{id}/send` | Send approved templates to leads |
| GET | `/api/outreach/campaigns/{id}/stats` | A/B analysis |
| PATCH | `/api/outreach/templates/{id}` | Edit / approve / reject template |
| GET | `/api/outreach/leads` | List leads |
| PATCH | `/api/outreach/leads/{id}` | Update lead |
| GET | `/api/outreach/contacts` | List contacts (CRM) |
| PATCH | `/api/outreach/contacts/{id}` | Update contact |
| GET | `/api/outreach/track/open/{send_id}` | Open pixel (no auth) |
| GET | `/api/outreach/unsubscribe/{send_id}` | Unsubscribe link (no auth) |

---

## File Map

| File | Purpose |
|---|---|
| `src/aiplatform/webapp/routers/outreach.py` | All HTTP endpoints |
| `src/aiplatform/skills/research/find_leads.py` | Lead discovery across channels |
| `src/aiplatform/skills/comms/compose_outreach.py` | A/B/C email composition |
| `src/aiplatform/skills/comms/analyze_outreach.py` | A/B analysis + open/reply tracking |
| `src/aiplatform/database/models.py` | Lead, OutreachCampaign, OutreachTemplate, OutreachSend, Contact |
| `src/aiplatform/worker.py` | Celery tasks: outreach.find_leads, outreach.send |
| `frontend/src/pages/Marketing.tsx` | Admin UI |
| `alembic/versions/b3f2a1d9e047_add_outreach_tables.py` | DB migration: outreach tables |
| `alembic/versions/c1d2e3f4a5b6_add_contacts_table.py` | DB migration: contacts table |

---

## Known Limitations / TODO

- Contact retention cleanup (12-month auto-expiry for approached/inquired) is not yet automated — add a scheduled Celery beat task.
- Re-subscribe flow for unsubscribed contacts is TBD.
- A/B variant assignment is guided by lead context during composition but not deterministically locked per send — future improvement.
- LinkedIn and ProductHunt channels are configured but require API keys not yet provisioned.
