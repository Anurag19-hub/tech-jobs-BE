
import os
import time
import threading

import httpx
from dotenv import load_dotenv
from firecrawl import Firecrawl

from app.services.link_discovery import filter_job_links


# --------------------------------------------------
# Environment configuration
# --------------------------------------------------

load_dotenv()

API_KEY = os.getenv("FIRECRAWL_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "FIRECRAWL_API_KEY is missing. Check your backend .env file."
    )

firecrawl = Firecrawl(api_key=API_KEY)


# --------------------------------------------------
# Request pacing and retry configuration
# --------------------------------------------------

MIN_REQUEST_INTERVAL = 7.5

# Rate-limit retries (HTTP 429)
MAX_RATE_LIMIT_RETRIES = 2

# Temporary network/timeout retries
MAX_NETWORK_RETRIES = 2

_request_lock = threading.Lock()
_last_request_time = 0.0


# --------------------------------------------------
# Utility functions
# --------------------------------------------------

def get_field(obj, name, default=None):
    """Read a field from a dictionary or an SDK response object."""
    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)


def is_rate_limit_error(exc: Exception) -> bool:
    """Recognize common HTTP 429 and Firecrawl rate-limit errors."""
    status_code = getattr(exc, "status_code", None)

    if status_code == 429:
        return True

    response = getattr(exc, "response", None)

    if getattr(response, "status_code", None) == 429:
        return True

    message = str(exc).lower()

    return (
        "429" in message
        or "rate limit" in message
        or "too many requests" in message
    )


# --------------------------------------------------
# Firecrawl request wrapper
# --------------------------------------------------

def call_firecrawl(operation):
    """
    Execute a Firecrawl request with shared pacing and
    limited retries for rate limits and temporary network errors.

    Rate limits use longer delays.
    Network timeouts use shorter delays.
    Other errors are raised immediately.
    """
    global _last_request_time

    rate_limit_attempts = 0
    network_attempts = 0

    while True:
        with _request_lock:
            elapsed = time.monotonic() - _last_request_time
            wait_seconds = MIN_REQUEST_INTERVAL - elapsed

            if wait_seconds > 0:
                time.sleep(wait_seconds)

            # Record the attempt time immediately before sending it.
            _last_request_time = time.monotonic()

            try:
                return operation()

            except Exception as exc:
                if is_rate_limit_error(exc):
                    if rate_limit_attempts >= MAX_RATE_LIMIT_RETRIES:
                        raise

                    rate_limit_attempts += 1
                    retry_delay = 30 * rate_limit_attempts

                elif isinstance(
                    exc,
                    (httpx.TimeoutException, httpx.NetworkError),
                ):
                    if network_attempts >= MAX_NETWORK_RETRIES:
                        raise

                    network_attempts += 1
                    retry_delay = 3 * network_attempts

                else:
                    raise

        # Sleep outside the lock so other callers are not blocked
        # during the retry delay.
        print(
            f"Firecrawl request failed temporarily: {error_name}. "
            f"Retrying in {retry_delay} seconds."
        )

        time.sleep(retry_delay)


# --------------------------------------------------
# Search response normalization
# --------------------------------------------------

def normalize_search_results(payload):
    """Normalize Firecrawl search responses into dictionaries."""
    data = (
        payload.get("data", payload)
        if isinstance(payload, dict)
        else payload
    )

    if isinstance(data, dict):
        results = (
            data.get("web")
            or data.get("results")
            or data.get("items")
            or []
        )
    elif isinstance(data, list):
        results = data
    else:
        results = []

    normalized = []

    for item in results:
        url = get_field(item, "url")
        title = get_field(item, "title")
        description = get_field(item, "description", "")

        if not isinstance(url, str) or not url:
            continue

        normalized.append({
            "title": title or "",
            "url": url,
            "description": description or "",
        })

    return normalized


# --------------------------------------------------
# Company career-page search
# --------------------------------------------------

def search_company_career_pages(
    query: str,
    limit: int = 5,
) -> list[dict]:
    """Search the web for real company and job-related pages."""

    def make_request():
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
            timeout=httpx.Timeout(
                60.0,
                connect=45.0,
            ),
        )

        response.raise_for_status()
        payload = response.json()

        if (
            isinstance(payload, dict)
            and payload.get("success") is False
        ):
            raise RuntimeError(
                "Firecrawl search request was unsuccessful."
            )

        return payload

    payload = call_firecrawl(make_request)
    results = normalize_search_results(payload)

    print(
        f"Firecrawl returned {len(results)} usable search results "
        f"for query: {query}"
    )

    return results


# --------------------------------------------------
# Job-link discovery from career pages
# --------------------------------------------------

def discover_job_links(career_url: str) -> dict[str, list[str]]:
    """Scrape a career page and classify its links."""

    result = call_firecrawl(
        lambda: firecrawl.scrape(
            career_url,
            formats=["links"],
        )
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
