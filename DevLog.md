# DevLog

Append a new row after every commit. Format: Date & Time (local, ISO 8601) | Jira Key | Commit ID (7 chars) | Description (why + what).

| Date & Time | Jira Key | Commit ID | Description |
|---|---|---|---|
| 2026-04-03 16:50 | | f40ccd8 | Fixed Etsy API list error response handling and tag truncation to 20 chars |
| 2026-04-03 16:57 | | 201faba | Filled all Etsy listing fields — shop section, AI disclosure, auto-renew |
| 2026-04-03 17:01 | | 30c0725 | Fixed job detail page — phase spinner, cancel button, scrollable data sections |
| 2026-04-03 17:17 | | 7068c0d | Fixed Phase 6 mockup/ZIP download from Drive — ephemeral containers can't rely on /tmp |
| 2026-04-03 17:36 | D-16 | d75f8df | Removed Phase 5 human review gate — Phase 4 now auto-chains to Phase 6 |
| 2026-04-03 17:47 | | d5b876c | Fixed themes endpoint — removed status filter, added Drive fallback |
| 2026-04-03 19:07 | | 8ca27f5 | Etsy Phase 7 promotion stub added |
| 2026-04-04 15:04 | D-18 | 5b59539 | Added public sample endpoints, Slack alerts, nurture emails, Fiverr parser, weekly digest |
| 2026-04-04 15:12 | | 25df011 | Added python-multipart to requirements for Form/File upload endpoints |
| 2026-04-04 15:19 | | 63825c5 | Fixed venture enum values in sample endpoints |
| 2026-04-04 15:26 | | 8797490 | Fixed Docker build — populate ai-marketing-claude submodule |
| 2026-04-04 15:33 | | eb2dd29 | Vendored ai-marketing-claude scripts as plain files, removed submodule |
| 2026-04-04 15:39 | | b80c693 | Added reportlab to requirements |
| 2026-04-04 21:31 | D-19 | 2cac676 | Fixed sample email delivery, Drive folder routing, job UUID navigation, Arabic font support |
| 2026-04-04 21:36 | | fd1fc38 | Fixed Drive uploads routing to correct EchoForge folders per venture |
| 2026-04-04 21:52 | | 3ba1cc4 | Added Slack alerts for new orders and review needed |
| 2026-04-04 22:12 | | e168719 | Added Testing checkbox to audit form; fixed Orders tab crash |
| 2026-04-04 22:26 | D-17 | 53af806 | Added multi-page BFS crawler to marketing audit — was homepage-only before |
| 2026-04-04 22:34 | | af297e1 | Fixed pipeline to upload to Drive before review gate; email client only after approval |
| 2026-04-05 05:59 | | 7457233 | Fixed sample email delivery and podcast sample 422 error |
| 2026-04-05 06:10 | | dcb1984 | Added openai to requirements — needed for Whisper transcription |
| 2026-04-05 06:13 | | 3c25f27 | Fixed delivery email to fall back to sample PDF Drive link for sample-only orders |
| 2026-04-05 06:14 | | 0808622 | Fixed demo=True handling in podcast pipeline when no audio file is provided |
| 2026-04-05 10:29 | AII-138 | cf0fe2d | Replaced URL input with file upload for podcast orders; added Drive OAuth logging |
| 2026-04-05 10:37 | | 3a0ced0 | Attempted to move Drive upload to worker (reverted — /tmp not shared between containers) |
| 2026-04-05 10:42 | AII-138 | bb05f21 | Fixed file access: audio must be uploaded to Drive in the web router, not the worker |
| 2026-04-05 10:49 | AII-138 | f076dc4 | Added proper error handling for audio upload failure and missing /tmp files |
| 2026-04-05 10:53 | AII-137 | 3642e14 | Fixed create_gdoc and drive_organise — both were hardcoded to service account, bypassing OAuth token |
| 2026-04-05 12:04 | AII-138 | 8aba884 | Added episode_title and host_name to podcast order form; fixed Google Doc sharing to be public link |
| 2026-04-05 12:20 | AII-138 | 5330919 | Added guest name and special instructions fields to podcast order form |
| 2026-04-05 14:00 | | 707cbb5 | Added DevLog.md, updated ROADMAP and CLAUDE.md files for D-20/D-21; added DevLog commit directive to root CLAUDE.md |
| 2026-04-05 14:30 | | 6ee51f7 | Replaced "Vercel" with "Cloudflare Pages" across CLAUDE.md, ROADMAP.md, src/aiplatform/CLAUDE.md — frontend is hosted on Cloudflare Pages |
| 2026-04-05 19:57 | | ace4c73 | Implemented Fiverr Gig Generator complete with platform webapp UI, backend endpoints, and cover image generation (H-08) |
| 2026-04-06 12:14 | | cc30cbb | Updated Fiverr Gig Generator with buyer requirements section |
| 2026-04-06 12:46 | | 20250ea | Updated Fiverr Gig Generator with strict length limits, package features, and audio length validation per tier via mutagen |
| 2026-04-06 13:41 | | 517aedd | Fixed Gig Generator package mappings (Title max 35 chars, Description max 100 chars) |
| 2026-04-06 13:41 |  | 12d95a4 | Fixed Gig Generator package mappings (Title max 35 chars, Description max 100 chars) |
| 2026-04-06 13:46 | | 85d8bf0 | Fixed FastAPI Pydantic schema stripping 'title' from Fiverr Gig Generator payload |
| 2026-04-06 15:58 | | 87892ea | Fixed UnicodeDecodeError in docker deployment caused by corrupted file encoding |
| 2026-04-06 15:40 | AII-0 | 80541d2 | Implemented system prompts editing UI in StrategyRoom and decoupled strings into platform registry markdown |
| 2026-04-06 16:30 | | 85d4399 | Fixed frontend ts build by removing unused roadmap import |
| 2026-04-06 16:33 | | b591314 | Corrected backend path to advisors.json in strategy router |
