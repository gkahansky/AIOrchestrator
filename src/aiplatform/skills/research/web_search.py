"""
Skill: web_search
Generic web search via SerpAPI — Google Search, Google Trends, Google Shopping.
Venture-agnostic: query construction happens in the calling pipeline.

Requires env var: SERPAPI_KEY

Functions:
    google_search(query, num_results)   → { organic_results, total_results, query }
    google_trends(query, period)        → { avg_interest, recent_interest, timeline }
    google_shopping(query, num_results) → { shopping_results }
"""

import os

import requests

SERPAPI_BASE = "https://serpapi.com/search.json"


def _get_key() -> str:
    key = os.environ.get("SERPAPI_KEY")
    if not key:
        raise EnvironmentError("SERPAPI_KEY is not set.")
    return key


def google_search(query: str, num_results: int = 10) -> dict:
    """
    Run a Google search and return organic results.

    Returns:
        {
            query         (str),
            total_results (int),
            organic_results: [{ title, link, snippet }]
        }
    """
    resp = requests.get(
        SERPAPI_BASE,
        params={"engine": "google", "q": query, "num": num_results, "api_key": _get_key()},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    total_str = data.get("search_information", {}).get("total_results", "0")
    try:
        total = int(str(total_str).replace(",", "").split(".")[0])
    except (ValueError, AttributeError):
        total = 0

    return {
        "query": query,
        "total_results": total,
        "organic_results": [
            {"title": r.get("title", ""), "link": r.get("link", ""), "snippet": r.get("snippet", "")}
            for r in data.get("organic_results", [])
        ],
    }


def google_trends(query: str, period: str = "today 3-m") -> dict:
    """
    Fetch Google Trends interest data for a query over the given period.

    Args:
        query:  Search term (e.g. 'botanical wall art print').
        period: SerpAPI date range — e.g. 'today 3-m', 'today 12-m'.

    Returns:
        {
            query           (str),
            avg_interest    (float),  # 0–100 average over period
            recent_interest (int),    # most recent data point
            peak_interest   (int),    # highest value in period
            timeline        (list),
        }
    """
    resp = requests.get(
        SERPAPI_BASE,
        params={"engine": "google_trends", "q": query, "date": period, "api_key": _get_key()},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    timeline = data.get("interest_over_time", {}).get("timeline_data", [])
    values = []
    for point in timeline:
        for v in point.get("values", []):
            try:
                values.append(int(v.get("extracted_value", 0)))
            except (TypeError, ValueError):
                pass

    return {
        "query":           query,
        "avg_interest":    round(sum(values) / len(values), 1) if values else 0,
        "recent_interest": values[-1] if values else 0,
        "peak_interest":   max(values) if values else 0,
        "timeline":        timeline,
    }


def google_shopping(query: str, num_results: int = 10) -> dict:
    """
    Fetch Google Shopping results for price benchmarking.

    Returns:
        {
            query            (str),
            shopping_results: [{ title, price, source, link }]
        }
    """
    resp = requests.get(
        SERPAPI_BASE,
        params={"engine": "google_shopping", "q": query, "num": num_results, "api_key": _get_key()},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    return {
        "query": query,
        "shopping_results": [
            {
                "title":  r.get("title", ""),
                "price":  r.get("price", ""),
                "source": r.get("source", ""),
                "link":   r.get("link", ""),
            }
            for r in data.get("shopping_results", [])
        ],
    }
