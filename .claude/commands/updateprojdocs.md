# updateprojdocs

Update all project documentation to reflect the current state of the codebase.

Run this skill after completing any feature, venture, or significant change before moving on to the next task.

## What to update

### 1. Venture CLAUDE.md (if a venture was touched)

For each venture directory modified (`src/ventures/{name}/`):
- Confirm the Pipeline Status table is accurate — mark completed features ✅, add new ones
- Update Environment Variables table if new env vars were added
- Update API Endpoints table if new routes were added
- Update the architecture notes if the pipeline structure changed
- If no CLAUDE.md exists for the venture yet, create one using the standard template below

**Standard venture CLAUDE.md template:**
```
# {Venture Name} Venture — CLAUDE.md
## What This Venture Is
## Directory Structure
## Pipeline Stages (table: stage | status field | what happens)
## Database Model (table of fields)
## API Endpoints (table)
## Environment Variables (table)
## Frontend (location + features)
## Key Skills Used (table)
## Architecture Constraints
## Pipeline Status (table: feature | status | notes)
```

### 2. Root CLAUDE.md (`/CLAUDE.md`)

- **Venture list** — if a new venture was added, append it to the venture list (Venture A, B, C…) and update the brand description line
- **Architecture Notes** — if the new venture introduces components not shared with others, add a `### Venture X — Name: Architecture Notes` block
- **Gig Generator** — if a new venture config was added to the Gig Generator, mention it in the Venture E architecture notes block
- **Feature list** — if a new feature or sub-module was added to an existing feature or venture, mention that under the relevant parent feature/venture section.

### 3. ToolStack.MD (`/ToolStack.MD`)

For any new external tool, API, library, or service introduced:
- Add a row to the appropriate section (AI & LLM, Google Platform, Database, etc.)
- If a tool was previously marked `*(planned)*`, update it to `*(live)*` or remove the qualifier
- Add any new environment variables to the "Environment Variables by Service" table at the bottom

### 4. DevLog.md (`/DevLog.md`)

Append a row for each commit made during this work session that doesn't already have a row:
```
| 2026-04-18 16:25 | AII-XXX | a2665fb | Short description of why + what |
```
- Date/time: local ISO 8601
- Jira Key: AII-XXX if related to a ticket, otherwise blank
- Commit ID: first 7 chars of the SHA (`git log --oneline -10` to find them)
- Description: one sentence — WHY the change was needed and WHAT it does

## Execution steps

1. Run `git log --oneline -10` to identify recent commits not yet in DevLog
2. Run `git diff HEAD~5 --name-only` to identify which ventures/files changed
3. For each changed venture, read its CLAUDE.md and update it
4. Update root CLAUDE.md if a new venture was added or architecture changed
5. Update ToolStack.MD for any new tools/services
6. Append missing rows to DevLog.md
7. Stage and commit: `git add -A && git commit -m "docs: update project docs post-feature"`
8. Push to remote

## What NOT to include in docs

- Code snippets (the code itself is the source of truth)
- Git history or who-changed-what (use `git log` for that)
- Temporary or in-progress state
- Anything already covered verbatim in the code (e.g. function signatures)
- Debugging steps or fix recipes

Focus on: **why the venture exists**, **what it does**, **how to operate it**, and **what's live vs planned**.
