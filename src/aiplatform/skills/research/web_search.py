"""
Skill: web_search
Generic web search — returns structured results for any query.

Status: Sprint 2 — not yet implemented.
Tool: SerpAPI (SERPAPI_KEY env var required).
"""


def web_search(query: str, num_results: int = 10) -> list[dict]:
    """
    Search the web and return structured results.

    Returns:
        [{ title, url, snippet }]
    """
    raise NotImplementedError("web_search is a Sprint 2 feature.")
