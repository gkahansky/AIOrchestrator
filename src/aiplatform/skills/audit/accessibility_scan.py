import asyncio
from datetime import datetime, timezone
from playwright.async_api import async_playwright
from axe_playwright_python.async_playwright import Axe

_AXE_OPTIONS = {"resultTypes": ["violations", "passes", "incomplete"]}

async def run_accessibility_scan(url: str, timeout_ms: int = 30000) -> dict:
    """
    Run an automated accessibility scan using axe-core and Playwright.
    
    Args:
        url: The website URL to scan.
        timeout_ms: Timeout for page load in milliseconds.

    Returns:
        dict: A structured dictionary containing Violations, Passes, and Incomplete nodes,
              as well as an overall wcag_score.
    """
    if not url.startswith('http'):
        url = f'http://{url}'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            # Wait until network is mostly idle to capture CSRF/SPA apps
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            
            axe = Axe()
            results = await axe.run(page, options=_AXE_OPTIONS)
            response = results.response if hasattr(results, "response") else results
            
            # axe-playwright-python returns an AxeResults wrapper with raw data in .response.
            # Normalise to plain dicts so the DB payload stays JSON-serialisable.
            
            # Serialize for DB storage
            def parse_result_nodes(rule_list):
                parsed = []
                for rule in rule_list:
                    rule_data = rule if isinstance(rule, dict) else vars(rule)
                    parsed.append({
                        "id": rule_data.get("id"),
                        "impact": rule_data.get("impact"),
                        "tags": rule_data.get("tags", []),
                        "description": rule_data.get("description"),
                        "help_url": rule_data.get("helpUrl") or rule_data.get("help_url"),
                        "nodes": [{
                            "target": node_data.get("target", []),
                            "html": node_data.get("html"),
                            "impact": node_data.get("impact"),
                            "failureSummary": node_data.get("failureSummary") or node_data.get("failure_summary")
                        } for node_data in [node if isinstance(node, dict) else vars(node) for node in rule_data.get("nodes", [])]]
                    })
                return parsed

            violations = parse_result_nodes(response.get("violations", []))
            passes = parse_result_nodes(response.get("passes", []))
            incomplete = parse_result_nodes(response.get("incomplete", []))

            # Basic score heuristic: based on amount and severity of violations.
            # Real score is typically derived from standard formulas.
            # Here we just want a basic heuristic: Max 100, -5 per critical, -3 per serious.
            critical_count = sum(len(v['nodes']) for v in violations if v.get('impact') == 'critical')
            serious_count = sum(len(v['nodes']) for v in violations if v.get('impact') == 'serious')
            moderate_count = sum(len(v['nodes']) for v in violations if v.get('impact') == 'moderate')
            minor_count = sum(len(v['nodes']) for v in violations if v.get('impact') == 'minor')

            score_deduction = (critical_count * 5) + (serious_count * 3) + (moderate_count * 1) + (minor_count * 0.5)
            wcag_score = max(0, 100 - score_deduction)

            return {
                "url": url,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "wcag_score": wcag_score,
                "violations": violations,
                "passes": passes,
                "incomplete": incomplete
            }
        finally:
            await browser.close()
