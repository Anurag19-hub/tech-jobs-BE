
from app.services.discovery_service import (
    search_company_career_pages,
    discover_job_links,
    firecrawl,
    get_field,
)
from app.services.job_extractor import extract_job_details


def main():
    print("Searching for Microsoft software engineering jobs...")

    results = search_company_career_pages(
        "Microsoft software engineering jobs India",
        limit=5,
    )

    # Find a Microsoft career page and discover individual job URLs.
    job_urls = []

    for item in results:
        url = item.get("url", "")

        if "careers.microsoft.com" not in url.lower():
            continue

        try:
            discovered = discover_job_links(url)
            job_urls.extend(discovered["job_detail_candidate"])
        except Exception as exc:
            print("Page discovery failed:", str(exc)[:200])

    # Remove duplicate URLs.
    job_urls = list(dict.fromkeys(job_urls))

    if not job_urls:
        print("No Microsoft job URLs discovered.")
        print("Search results:")

        for item in results:
            print(item.get("title"), item.get("url"))

        return

    job_url = job_urls[0]

    print("\nScraping discovered job:")
    print(job_url)

    result = firecrawl.scrape(
        job_url,
        formats=["markdown"],
    )

    data = get_field(result, "data", result)
    markdown = get_field(data, "markdown", "") or ""

    if not markdown:
        print("No Markdown content returned.")
        return

    # Extract fields using our reusable job extractor.
    job = extract_job_details(job_url, markdown)

    print("\n--- EXTRACTED MICROSOFT JOB ---")

    for key, value in job.items():
        if key == "description":
            print("description_length:", len(value or ""))
            print("description_preview:")
            print((value or "")[:1000])
        else:
            print(f"{key}: {value}")

    print("\n--- VALIDATION ---")

    required_fields = [
        "title",
        "company",
        "location",
        "source_job_id",
        "source_url",
    ]

    for field in required_fields:
        value = job.get(field)
        print(f"{field}: {'OK' if value else 'MISSING'}")

    if job.get("description") and len(job["description"]) <= 30000:
        print("description_size: OK")
    else:
        print("description_size: CHECK")


if __name__ == "__main__":
    main()
