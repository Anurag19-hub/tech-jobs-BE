
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.database import supabase
from app.services.discovery_service import (
    search_company_career_pages,
    discover_job_links,
    firecrawl,
    get_field,
    call_firecrawl,
)
from app.services.job_extractor import (
    extract_job_details,
    get_company_from_url,
)
from app.services.ingestion_service import ingest_jobs


router = APIRouter(
    prefix="/api/v1/collection",
    tags=["Collection"],
)


class CollectionRequest(BaseModel):
    queries: list[str] = Field(
        default_factory=lambda: [
            "IBM careers jobs India",
            "Microsoft careers jobs India",
        ],
        min_length=1,
        max_length=5,
    )
    max_jobs: int = Field(default=10, ge=1, le=20)
    dry_run: bool = True


def verify_collection_key(
    supplied_key: str | None,
) -> None:
    """Reject collection requests without the configured secret."""
    expected_key = settings.collection_api_key

    if not expected_key:
        raise HTTPException(
            status_code=503,
            detail="Collection endpoint is not configured.",
        )

    if not supplied_key or not secrets.compare_digest(
        supplied_key,
        expected_key,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid collection API key.",
        )


def create_collection_log(dry_run: bool) -> int:
    """Create a collection log and return its generated ID."""
    result = (
        supabase.table("collection_logs")
        .insert({
            "source_name": "Firecrawl Search",
            "workflow_name": (
                "api_collection_dry_run"
                if dry_run
                else "api_collection_live"
            ),
            "status": "running",
            "records_found": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        .execute()
    )

    if not result.data:
        raise RuntimeError("Could not create collection log.")

    return result.data[0]["id"]


def update_collection_log(
    log_id: int,
    status: str,
    records_found: int = 0,
    records_inserted: int = 0,
    records_updated: int = 0,
    error_message: str | None = None,
) -> None:
    """Finish the collection log."""
    payload = {
        "status": status,
        "records_found": records_found,
        "records_inserted": records_inserted,
        "records_updated": records_updated,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    if error_message:
        payload["error_message"] = error_message[:2000]

    (
        supabase.table("collection_logs")
        .update(payload)
        .eq("id", log_id)
        .execute()
    )


def is_job_detail_url(url: str) -> bool:
    """Identify likely individual job-detail URLs."""
    parsed = urlparse(url)
    path = parsed.path.lower()

    return (
        "/jobdetail" in path
        or "/careers/job/" in path
        or "/careers/jobs/" in path
        or "/jobs/" in path
        or "/job/" in path
        or "/positions/" in path
    )


def discover_candidate_urls(
    query: str,
    max_candidates: int,
) -> list[str]:
    """
    Discover job URLs while limiting unnecessary career-page scrapes.

    Direct job-detail results are prioritized. At most two additional
    non-detail pages are inspected for each query.
    """
    search_results = search_company_career_pages(
        query,
        limit=5,
    )

    candidate_urls = []
    pages_to_inspect = []

    # Prefer search results that already point to individual job pages.
    for result in search_results:
        page_url = result.get("url", "")

        if not page_url or not get_company_from_url(page_url):
            continue

        if is_job_detail_url(page_url):
            candidate_urls.append(page_url)
        else:
            pages_to_inspect.append(page_url)

    # Remove duplicate direct results.
    candidate_urls = list(dict.fromkeys(candidate_urls))

    if len(candidate_urls) >= max_candidates:
        return candidate_urls[:max_candidates]

    # Only inspect up to two additional pages per query.
    pages_to_inspect = list(dict.fromkeys(pages_to_inspect))[:2]

    for page_url in pages_to_inspect:
        try:
            discovered = discover_job_links(page_url)

            for url in discovered.get("job_detail_candidate", []):
                if get_company_from_url(url):
                    candidate_urls.append(url)

            candidate_urls = list(dict.fromkeys(candidate_urls))

            if len(candidate_urls) >= max_candidates:
                break

        except Exception as exc:
            # One inaccessible page should not stop other discovery.
            print(
                f"Could not inspect career page {page_url}: "
                f"{str(exc)[:200]}"
            )

    return candidate_urls[:max_candidates]


def scrape_job(url: str) -> dict | None:
    """Scrape and extract one candidate job page with rate-limit handling."""
    result = call_firecrawl(
        lambda: firecrawl.scrape(
            url,
            formats=["markdown"],
        )
    )

    data = get_field(result, "data", result)
    markdown = get_field(data, "markdown", "") or ""

    if not markdown:
        return None

    job = extract_job_details(url, markdown)

    if not job.get("title") or not job.get("company"):
        return None

    return job


@router.post("/run")
def run_collection(
    request: CollectionRequest,
    x_collection_key: str | None = Header(
        default=None,
        alias="X-Collection-Key",
    ),
):
    """Trigger a protected collection run."""
    verify_collection_key(x_collection_key)

    try:
        log_id = create_collection_log(request.dry_run)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not start the collection log.",
        ) from exc

    extracted_jobs = []
    scrape_errors = []
    candidate_urls = []

    try:
        # Search each requested query.
        per_query_limit = max(
            1,
            request.max_jobs // len(request.queries),
        )

        for query in request.queries:
            try:
                urls = discover_candidate_urls(
                    query,
                    per_query_limit,
                )
                candidate_urls.extend(urls)

            except Exception as exc:
                scrape_errors.append({
                    "query": query,
                    "error": str(exc)[:300],
                })

        # Remove duplicate URLs and apply the requested limit.
        candidate_urls = list(dict.fromkeys(candidate_urls))
        candidate_urls = candidate_urls[:request.max_jobs]

        # Scrape each unique candidate URL.
        for url in candidate_urls:
            try:
                time.sleep(1.5)
                job = scrape_job(url)

                if job:
                    extracted_jobs.append(job)

            except Exception as exc:
                scrape_errors.append({
                    "url": url,
                    "error": str(exc)[:300],
                })

        # Dry-run is the default; live writes require explicit request.
        report = ingest_jobs(
            extracted_jobs,
            dry_run=request.dry_run,
        )

        all_errors = scrape_errors + report["errors"]
        rejected_count = len(report["rejected"])

        if all_errors:
            status = (
                "partial_failure"
                if extracted_jobs or report["valid_records"]
                else "failed"
            )
        elif rejected_count:
            status = "partial_failure"
        else:
            status = "success"

        # Count successful database actions only in live mode.
        inserted = 0
        updated = 0

        if not request.dry_run:
            failed_titles = {
                item.get("title")
                for item in report["errors"]
            }

            for action in report["actions"]:
                if action.get("title") in failed_titles:
                    continue

                if action.get("action") == "insert":
                    inserted += 1
                elif action.get("action") == "update":
                    updated += 1

        # Update the collection log.
        update_collection_log(
            log_id=log_id,
            status=status,
            records_found=len(extracted_jobs),
            records_inserted=inserted,
            records_updated=updated,
            error_message=(
                "; ".join(
                    str(item.get("error", item))
                    for item in all_errors
                )
                if all_errors
                else None
            ),
        )

        # Return the extraction preview for verification.
        return {
            "message": "Collection run finished.",
            "log_id": log_id,
            "mode": report["mode"],
            "status": status,
            "queries": request.queries,
            "candidate_urls": len(candidate_urls),
            "records_extracted": len(extracted_jobs),
            "valid_records": report["valid_records"],
            "extracted_preview": [
                {
                    "company": job.get("company"),
                    "title": job.get("title"),
                    "location": job.get("location"),
                    "job_type": job.get("job_type"),
                    "source_job_id": job.get("source_job_id"),
                    "source_url": job.get("source_url"),
                    "apply_url": job.get("apply_url"),
                }
                for job in extracted_jobs
            ],
            "rejected": report["rejected"],
            "errors": all_errors,
            "ingestion_report": report,
        }

    except Exception as exc:
        try:
            update_collection_log(
                log_id=log_id,
                status="failed",
                records_found=len(extracted_jobs),
                error_message=str(exc),
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail="Collection failed. Check collection_logs.",
        ) from exc
