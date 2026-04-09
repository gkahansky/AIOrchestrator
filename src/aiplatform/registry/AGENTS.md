# Advisory Board — Agents & Capabilities

---

Architect:
 - Review GitHub pull requests for code quality, SOLID principles, and security flaws
 - Identify technical debt and flag poorly structured DB queries or bloated API calls
 - Propose tech-debt items to be added to the platform roadmap
 - Triggered automatically on every PR opened or synchronized via GitHub webhook
 - TODO: Scan repository for dependency vulnerabilities on a scheduled basis
 - TODO: Post inline code review comments directly on the GitHub PR

---

Marketing:
 - Monitor product listings and identify dead inventory with zero traction
 - Review recent revenue events and evaluate pricing model effectiveness
 - Recommend promotional audits and suggest new gig/service features based on market shifts
 - Propose tag and price optimizations to maximize conversion rates and ROAS
 - TODO: Triggered automatically when revenue drops below a rolling weekly threshold
 - TODO: Monitor competitor pricing and surface repricing recommendations

---

Product:
 - Analyse completed pipeline jobs for duration, phase bottlenecks, and cost efficiency
 - Identify inefficiencies in Human-in-the-Loop review cycles (e.g. review_pending → approved lag)
 - Suggest automation opportunities to reduce manual intervention
 - Triggered automatically after every completed pipeline job (Celery task_success signal)
 - TODO: Triggered automatically when job cost exceeds a per-venture budget threshold
 - TODO: Score and prioritize backlog items by effort-to-margin ratio

---

Executive:
 - Consume the weekly financial digest (cost vs revenue across all ventures)
 - Assess macro trends and identify resource misallocation across the portfolio
 - Formulate the Weekly Business Overview and declare strategic focus for upcoming sprints
 - Hold directional influence over Architect, Product, and Marketing advisor priorities
 - Triggered automatically every Monday at 08:00 UTC via Celery Beat
 - TODO: Cross-reference advisor proposals from all agents and synthesize a unified weekly action plan
 - TODO: Trigger ad-hoc review when net margin falls below a configurable threshold
