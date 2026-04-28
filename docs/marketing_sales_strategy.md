# Marketing & Sales Strategy
## EchoForge + MiroPrintStudio — Go-To-Market Plan

> Last updated: 2026-04-08
> All 4 income streams are fully built and tested. This document tracks what is done, what is missing, and what to build next to drive traffic and acquire customers.

---

## 1. MiroPrintStudio — Etsy Digital Art

**Pipeline status:** Phases 1–6 live and automated.

### Current State
- ✅ 29 listings published, 12+ in drafts — publishing 2–3 every other day
- ✅ Shop logo and banner in place
- ✅ Facebook, Instagram, and YouTube channels set up
- ❌ Shop bio, About section, and policies (returns, delivery) missing — hurts trust and Etsy SEO
- ❌ No content posted to any social channel yet
- ❌ Phase 7 not built (Etsy Ads auto-enrol + Buffer social queue)
- ❌ Zero reviews — low trust for new buyers

### What to Do

| Action | Type | Priority |
|---|---|---|
| Write shop bio, About section, and store policies | Manual (30 min) | Urgent |
| Post first mockup images to Instagram and Facebook | Manual (today) | High |
| Build Phase 7 — Etsy Ads enrol at $1–2/day via Etsy Ads API | Dev | High |
| Build Phase 7 — Buffer social queue (Instagram + Facebook) | Dev | High |
| Seed first 1–2 reviews (free download offer to someone you know) | Manual | High |
| Run Etsy Ads at $1/day on 3 listings for 2 weeks to validate price point | Manual ($14) | Medium |

---

## 2. Marketing Audit Reports — EchoForge

**Pipeline status:** Full pipeline live. PDF generation, Drive upload, review gate, delivery email. Free sample endpoint live at `POST /api/sample/audit`.

### Current State
- ✅ Fiverr gig published
- ✅ echoforge.biz has pricing page, three tiers ($49/$149/$249), and free sample lead-gen form at `/try-audit`
- ✅ Sample report generates censored PDF (score + dimensions visible; findings/actions unlocked after purchase)
- ✅ Accessibility scan auto-injected on Premium tier (hard-coded in pipeline)
- ❌ Cold outreach pipeline not built (M-10) — this is the primary proactive acquisition channel
- ❌ No reviews or orders yet — need first customers

### What to Do

| Action | Type | Priority |
|---|---|---|
| Build M-10: cold outreach pipeline — scan prospect site → generate sample → send personalised cold email | Dev | High |
| Surface M-10 in planBadmin.com — trigger and manage outreach from admin UI | Dev | High |
| Manually run the pipeline on 5 prospect sites and send cold emails this week | Manual | High |
| Review echoforge.biz CTA copy — ensure "Get Free Audit" is above the fold | Manual | Medium |
| Decide: Stripe independent billing vs Fiverr-only | Decision | Medium |

---

## 3. Accessibility Audit — EchoForge

**Pipeline status:** Full Playwright/axe-core scanner live. PDF report, all API endpoints working. Admin UI trigger live.

### Current State
- ✅ Service exists on echoforge.biz — standalone pricing ($120 / $250) and free sample at `/try-accessibility`
- ✅ Bundled into Marketing Audit Premium tier — hard-coded in `marketing_audit/pipeline.py`
- ✅ Premium marketing audit description on echoforge.biz mentions accessibility coverage
- ❌ No Fiverr gig — can't find a suitable Fiverr category that fits WCAG/accessibility auditing
- ❌ Scope gap: current report is axe-core automated only (~30% of WCAG coverage). All public listings must say "automated WCAG scan" not "full WCAG audit"

### What to Do

| Action | Type | Priority |
|---|---|---|
| Research Fiverr categories — "Website Audit", "UX Design", or "SEO" may be the best fit for a WCAG accessibility gig | Research | High |
| Once category found, run Gig Generator and publish | Dev/Manual | High |
| Add explicit upsell on marketing audit order form: "Add standalone accessibility report +$120" | Dev | Medium |
| Clarify scope in all listings: "Automated WCAG 2.1/2.2 scan via axe-core" | Manual | Medium |

---

## 4. Podcast Show Notes — EchoForge

**Pipeline status:** Full pipeline live (transcription → content → PDF). Sample endpoint live at `POST /api/sample/podcast`. File upload form live.

### Current State
- ✅ Fiverr gig published
- ✅ echoforge.biz has pricing ($49/$79/$119), service page, and free 10-minute sample form at `/try-podcast`
- ✅ Brand Voice Guide add-on implemented (`generate_brand_voice.py`, 185 lines, wired into pipeline)
- ✅ Promo Copy add-on implemented (`generate_promo_copy.py`, 157 lines, wired into pipeline)
- ❌ Fiverr gig extras not yet configured for add-ons (Brand Voice $79, Promo Copy $39)
- ❌ Social Calendar add-on — not built (`generate_social_calendar.py` missing)
- ❌ Email Sequence add-on — not built (`generate_email_sequence.py` missing)
- ❌ Guest Outreach Templates — not built (`generate_guest_outreach.py` missing)
- ❌ Podcast Launch Playbook — not built (`generate_launch_playbook.py` missing)
- ❌ Zero reviews — need first customers

### What to Do

| Action | Type | Priority |
|---|---|---|
| Configure Fiverr gig extras for Brand Voice ($79) and Promo Copy ($39) — already implemented in code | Manual (30 min) | Urgent |
| Post in r/podcasting and 1–2 Facebook podcast groups — offer first order free for a review | Manual | High |
| Build Sprint 4b: `generate_social_calendar.py` (highest-value upsell at $79) | Dev | High |
| Build Sprint 4b: `generate_email_sequence.py` ($99 add-on) | Dev | High |
| Build Sprint 5b: `generate_guest_outreach.py` ($29 add-on) | Dev | Medium |

---

## Cross-Stream: Shared Infrastructure Gaps

### Marketplace Presence

| Channel | Status |
|---|---|
| EchoForge Fiverr account | Almost complete — missing accessibility audit gig (1 gig remaining) |
| Marketing Audit gig | ✅ Published |
| Podcast Show Notes gig | ✅ Published |
| Accessibility Audit gig | ❌ Missing — Fiverr category TBD |
| Independent billing (Stripe) | 🤔 Under consideration — would remove platform fees and unlock custom offerings |

### echoforge.biz

| Page | Status |
|---|---|
| Marketing Audit pricing + free sample form | ✅ Live at `/try-audit` |
| Podcast pricing + free sample form | ✅ Live at `/try-podcast` |
| Accessibility pricing + free sample form | ✅ Live at `/try-accessibility` |
| Blog / SEO content | ❌ Not started — long-term organic traffic driver |

---

## What to Build Next (Dev Priorities)

### Sprint: Cold Outreach + Promotion Automation

These two are the highest-leverage things to build. Everything else is polishing a product nobody is seeing yet.

#### 1. Cold Outreach Pipeline (M-10)
**Goal:** Automatically scan a prospect's website → generate a personalised sample audit → send a cold email with 3 specific findings.

- Skill: `research/find_leads.py` — takes a target list (industry/location/type)
- Skill: `media/generate_offer_sheet.py` — personalised one-page PDF from sample audit data
- Pipeline: `ventures/marketing_audit/outreach_pipeline.py`
- **Admin UI:** Outreach queue page in planBadmin.com — trigger campaigns, track sent/opened/replied, approve emails before send
- Output stored in `/platform/leads/marketing_audit/` in Drive

#### 2. Promotion Agent (H-10)
**Goal:** Automatically post to relevant communities across all ventures on a schedule.

- Channels: Reddit (r/podcasting, r/etsy, r/webdesign), Facebook groups, LinkedIn
- Per-venture config: target subreddits, groups, post templates, rate limits
- Rate-limited and de-duplicated per platform per post
- Skill: `comms/promote_venture.py`
- **Admin UI:** Promotion queue and schedule visible in planBadmin.com

#### 3. Podcast Sprint 4b Add-ons
- `generate_social_calendar.py` — 30-day social calendar from 4 episodes ($79)
- `generate_email_sequence.py` — 5-email listener nurture sequence ($99)

---

## Recommended Sequence

### This Week — No Code Required
- [ ] Write MiroPrintStudio shop bio, About section, and store policies (30 min)
- [ ] Post first 2–3 mockups to Instagram and Facebook manually
- [ ] Configure Fiverr gig extras for Brand Voice and Promo Copy add-ons (30 min)
- [ ] Research Fiverr category for Accessibility Audit gig
- [ ] Manually run marketing audit pipeline on 5 prospect sites and send cold emails

### Next Sprint — Dev
- [ ] Build cold outreach pipeline (M-10) with planBadmin.com UI
- [ ] Build Phase 7 for Etsy (Etsy Ads API + Buffer social queue)
- [ ] Build `generate_social_calendar.py` and `generate_email_sequence.py` for podcast
- [ ] Run Gig Generator for accessibility audit once category is decided

### Following Sprint — Growth Automation
- [ ] Build Promotion Agent (H-10) — Reddit, Facebook, LinkedIn
- [ ] Build `generate_guest_outreach.py` and `generate_launch_playbook.py`
- [ ] Add Stripe billing option for direct sales (decision pending)
- [ ] Enable AUTO_APPROVE after 20 validated deliveries per venture

---

> **The product works and the storefronts are open. The gap is active outreach and promotion — both of which can be automated.**
