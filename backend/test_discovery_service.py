
from app.services.discovery_service import (
    search_company_career_pages,
    discover_job_links,
)

print("Searching for Indian software company careers...")

try:
    results = search_company_career_pages(
        "India software company careers jobs",
        limit=5,
    )

    print(f"\nSearch Results: {len(results)}")

    if not results:
        print("No usable URLs returned. Check the raw API response next.")

    for index, item in enumerate(results[:3], 1):
        title = item["title"]
        url = item["url"]

        print(f"\n{index}. {title or 'Untitled page'}")
        print(url)

        try:
            discovered = discover_job_links(url)

            print(
                "Job Detail Candidates:",
                len(discovered["job_detail_candidate"]),
            )
            print(
                "Career Pages:",
                len(discovered["career_page"]),
            )
            print(
                "Job Search Pages:",
                len(discovered["job_search"]),
            )

            for job_url in discovered["job_detail_candidate"][:3]:
                print("  Job candidate:", job_url)

        except Exception as exc:
            print("Crawl failed:", type(exc).__name__, str(exc)[:250])

except Exception as exc:
    print("\nDiscovery failed:", type(exc).__name__, str(exc)[:500])
