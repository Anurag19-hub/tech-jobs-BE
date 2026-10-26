
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
    r"\.(?:png|jpg|jpeg|gif|svg|pdf|zip|css|js)(?:$|\?)",
]

JOB_DETAIL_PATTERNS = [
    r"/(?:jobs?|positions?)/[^/]+/?$",
    r"/careers?/job/[^/]+/?$",
    r"/careers?/jobs?/[^/]+/?$",
    r"/jobdetail/?$",
]

JOB_LISTING_PATTERNS = [
    r"/(?:careers?/)?(?:search|job-search|jobs-search|openings)/?$",
    r"/(?:careers?/)?(?:jobs|positions)/?$",
]


def classify_url(url: str) -> str:
    """
    Classify a URL by its structure.
    This does not prove that a job is currently open.
    """
    if not isinstance(url, str):
        return "ignore"

    url = url.strip()

    if not url.startswith(("http://", "https://")):
        return "ignore"

    clean_url, _ = urldefrag(url)
    parsed = urlparse(clean_url)
    path = parsed.path.lower()

    params = {
        key.lower(): values
        for key, values in parse_qs(parsed.query).items()
    }

    if any(
        re.search(pattern, path)
        for pattern in EXCLUDE_PATTERNS
    ):
        return "ignore"

    # IBM and similar platforms often identify vacancies by query ID.
    if (
        "jobdetail" in path
        and any(
            key in params
            for key in ("jobid", "job_id", "reqid", "pid")
        )
    ):
        return "job_detail_candidate"

    # Common individual vacancy URL patterns.
    if any(
        re.search(pattern, path)
        for pattern in JOB_DETAIL_PATTERNS
    ):
        return "job_detail_candidate"

    # Listing/search pages are useful, but may not be individual jobs.
    if any(
        re.search(pattern, path)
        for pattern in JOB_LISTING_PATTERNS
    ):
        return "job_search"

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

        category = classify_url(clean_url)

        if category == "ignore":
            continue

        # Ignore tracking fragments and remove duplicate URLs.
        if clean_url in seen:
            continue

        seen.add(clean_url)
        grouped[category].append(clean_url)

    # Individual job pages first, followed by listings and career pages.
    return {
        "job_detail_candidate": grouped["job_detail_candidate"],
        "job_search": grouped["job_search"],
        "career_page": grouped["career_page"],
        "other": grouped["other"],
    }
