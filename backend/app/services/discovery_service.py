
import os

import httpx
from dotenv import load_dotenv
from firecrawl import Firecrawl

from app.services.link_discovery import filter_job_links


load_dotenv()

API_KEY = os.getenv("FIRECRAWL_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "FIRECRAWL_API_KEY is missing. Check your backend .env file."
    )

firecrawl = Firecrawl(api_key=API_KEY)


def get_field(obj, name, default=None):
    """Read a field from a dictionary or an SDK response object."""
    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)


def normalize_search_results(payload):
    """Normalize Firecrawl search responses into a list of dictionaries."""

    data = payload.get("data", payload) if isinstance(payload, dict) else payload

    if isinstance(data, dict):
        results = data.get("web")

        if results is None:
            results = data.get("results")

        if results is None:
            results = data.get("items")

        if results is None:
            results = []

    elif isinstance(data, list):
        results = data

    else:
        results = []

    normalized = []

    for item in results:
        url = get_field(item, "url")
        title = get_field(item, "title")
        description = get_field(item, "description", "")

        if not url or not isinstance(url, str):
            continue

        normalized.append({
            "title": title or "",
            "url": url,
            "description": description or "",
        })

    return normalized


def search_company_career_pages(
    query: str,
    limit: int = 5,
) -> list[dict]:
    """Search the web for real company and job-related pages."""

    response = httpx.post(
        "https://api.firecrawl.dev/v2/search",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "query": query,
            "limit": limit,
        },
        timeout=60.0,
    )

    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, dict) and payload.get("success") is False:
        raise RuntimeError("Firecrawl search request was unsuccessful.")

    results = normalize_search_results(payload)

    print(f"Firecrawl returned {len(results)} usable search results.")

    return results


def discover_job_links(career_url: str) -> dict[str, list[str]]:
    """Scrape a page and classify the links it contains."""

    result = firecrawl.scrape(
        career_url,
        formats=["links"],
    )

    data = get_field(result, "data", result)
    raw_links = get_field(data, "links", None)

    if raw_links is None:
        raw_links = get_field(result, "links", [])

    if not isinstance(raw_links, list):
        raw_links = []

    links = []

    for item in raw_links:
        if isinstance(item, str):
            links.append(item)
        else:
            link = get_field(item, "url")
            if isinstance(link, str):
                links.append(link)

    return filter_job_links(links)
