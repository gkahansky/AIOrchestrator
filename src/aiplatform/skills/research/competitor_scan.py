"""
Skill: competitor_scan
Scan competitor Etsy listings for a keyword via SerpAPI Google Search.
Returns listing count (competition volume) and price data (monetisation signal).

Requires env var: SERPAPI_KEY
"""

import re

from aiplatform.skills.research.web_search import google_search, google_shopping


def scan_etsy_listings(keyword: str, num_results: int = 10) -> dict:
    """
    Search Google for site:etsy.com listings matching the keyword.

    Returns:
        {
            keyword       (str),
            listing_count (int),   # estimated total Etsy listings
            avg_price_usd (float), # average price from visible listings
            prices        (list),  # raw prices found
            top_titles    (list),  # top listing titles
        }
    """
    query = f'site:etsy.com "{keyword}" digital download print'
    result = google_search(query, num_results=num_results)

    prices = _extract_prices(result["organic_results"])
    titles = [r["title"] for r in result["organic_results"] if r["title"]]

    avg_price = round(sum(prices) / len(prices), 2) if prices else 0.0

    return {
        "keyword":       keyword,
        "listing_count": result["total_results"],
        "avg_price_usd": avg_price,
        "prices":        prices,
        "top_titles":    titles[:5],
    }


def scan_etsy_prices(keyword: str) -> dict:
    """
    Use Google Shopping to get cleaner price data for a keyword on Etsy.

    Returns:
        {
            keyword       (str),
            avg_price_usd (float),
            prices        (list),
        }
    """
    query = f"{keyword} digital print etsy"
    result = google_shopping(query, num_results=10)

    prices = []
    for item in result["shopping_results"]:
        price_str = item.get("price", "")
        parsed = _parse_price(price_str)
        if parsed and parsed <= 50:   # cap at $50 — filter outliers
            prices.append(parsed)

    avg_price = round(sum(prices) / len(prices), 2) if prices else 4.99

    return {
        "keyword":       keyword,
        "avg_price_usd": avg_price,
        "prices":        prices,
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_prices(organic_results: list[dict]) -> list[float]:
    """Extract prices from organic result snippets using regex."""
    prices = []
    for r in organic_results:
        text = r.get("snippet", "") + " " + r.get("title", "")
        for match in re.findall(r'\$\s?(\d+\.?\d*)', text):
            try:
                p = float(match)
                if 0.50 <= p <= 50:
                    prices.append(p)
            except ValueError:
                pass
    return prices


def _parse_price(price_str: str) -> float | None:
    """Parse a price string like '$4.99' or '4.99 USD' to float."""
    match = re.search(r'(\d+\.?\d*)', price_str.replace(",", ""))
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None
