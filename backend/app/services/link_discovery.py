
import re
from urllib.parse import urlparse, urldefrag, parse_qs


EXCLUDE_PATTERNS = [
    r"/blog(?:/|$)",
    r"/news(?:/|$)",
    r"/events?(?:/|$)",
    r"/privacy(?:/|$)",
    r"/terms(?:/|$)",
    r"/login(?:/|$)",
    r"/sign-?in(?:/|$)",
    r"/support(?:/|$)",
    r"/contact(?:/|$)",
    r"/jobalerts?(?:/|$)",
    r"\.(?:png|jpg|jpeg|gif|svg|pdf|zip|css|js)$",
]


def classify_url(url: str) -> str:
    """
    Classify a URL for discovery.
    Classification is based on URL structure, not proof
    that a job is currently open.
    """
    if not url or not url.startswith(("http://", "https://")):
        return "ignore"

    clean_url, _ = urldefrag(url.strip())
    parsed = urlparse(clean_url)
    path = parsed.path.lower()
    params = {
        key.lower(): values
        for key, values in parse_qs(parsed.query).items()
    }

    if any(re.search(pattern, path) for pattern in EXCLUDE_PATTERNS):
        return "ignore"

    # IBM-style individual vacancy pages.
    if (
        "jobdetail" in path
        and any(key in params for key in ("jobid", "job_id", "reqid"))
    ):
        return "job_detail_candidate"

    # Common job-detail URL patterns on other career platforms.
    if re.search(r"/(?:jobs?|positions?)/[^/]+/?$", path):
        return "job_detail_candidate"

    # Search or listing pages may contain many vacancies.
    if re.search(
        r"/(?:careers?/)?(?:search|job-search|jobs-search|openings)/?$",
        path,
    ):
        return "job_search"

    # Career pages are useful starting points for further crawling.
    if re.search(r"/careers?(?:/|$)", path):
        return "career_page"

    return "other"


def filter_job_links(links: list[str]) -> dict[str, list[str]]:
    """Deduplicate URLs and group them by likely purpose."""
    grouped = {
        "job_detail_candidate": [],
        "job_search": [],
        "career_page": [],
        "other": [],
    }
    seen = set()

    for link in links:
        if not isinstance(link, str):
            continue

        clean_url, _ = urldefrag(link.strip())

        if not clean_url or clean_url in seen:
            continue

        seen.add(clean_url)
        category = classify_url(clean_url)

        if category in grouped:
            grouped[category].append(clean_url)

    return grouped
