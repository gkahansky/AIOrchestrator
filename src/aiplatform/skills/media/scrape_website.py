"""
Skill: scrape_website
Fetch and analyse a website's marketing elements using the ai-marketing-claude analyzer.

Input:
    url               (str):       Target URL (https:// prepended if missing).
    competitor_urls   (list[str]): Optional URLs of competitor sites to scan.

Output:
    {
        "target":      dict,  # analyze_page.analyze() result for the main URL
        "competitors": list,  # scan_competitor() results (empty list if none provided)
    }

Requires: AI_MARKETING_CLAUDE_PATH env var (or sibling repo convention):
    C:\\Projects\\AI\\
        AIOrchestrator\\   ← this repo
        ai-marketing-claude\\
"""

import os
import sys
from pathlib import Path
from typing import Optional


def _scripts_path() -> str:
    """Resolve the ai-marketing-claude scripts directory."""
    env_path = os.environ.get("AI_MARKETING_CLAUDE_PATH", "")
    if env_path:
        return str(Path(env_path) / "scripts")
    # Convention: sibling repo at ../../ai-marketing-claude relative to repo root
    repo_root = Path(__file__).parent.parent.parent.parent.parent.parent
    return str(repo_root / "ai-marketing-claude" / "scripts")


def _import_analyzers():
    scripts = _scripts_path()
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        from analyze_page import analyze
        from competitor_scanner import scan_competitor, scan_multiple
        return analyze, scan_competitor, scan_multiple
    except ImportError as exc:
        raise ImportError(
            f"Could not import from ai-marketing-claude scripts at {scripts}. "
            "Set AI_MARKETING_CLAUDE_PATH=<path to ai-marketing-claude repo root> in .env. "
            f"Original error: {exc}"
        )


def scrape_website(
    url: str,
    competitor_urls: Optional[list] = None,
) -> dict:
    """
    Scrape the target site and any competitor sites.

    Returns:
        {
            "target":      dict,  # Full analyze_page result
            "competitors": list,  # scan_competitor results for each competitor URL
        }
    """
    if not url.startswith("http"):
        url = "https://" + url

    analyze, scan_competitor, scan_multiple = _import_analyzers()

    target = analyze(url)
    if target.get("status") == "error":
        raise ValueError(f"Failed to scrape {url}: {target.get('message')}")

    competitors = []
    if competitor_urls:
        for comp_url in competitor_urls:
            if not comp_url.startswith("http"):
                comp_url = "https://" + comp_url
            comp = scan_competitor(comp_url)
            competitors.append(comp)

    return {"target": target, "competitors": competitors}
