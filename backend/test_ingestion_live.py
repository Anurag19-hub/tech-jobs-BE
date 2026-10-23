
from app.services.discovery_service import firecrawl, get_field
from app.services.job_extractor import extract_job_details
from app.services.ingestion_service import ingest_jobs


TEST_URLS = [
    (
        "https://careers.ibm.com/en_US/careers/JobDetail"
        "?jobId=137471&source=WEB_Sweng_NA"
    ),
    (
        "https://apply.careers.microsoft.com/careers/job/"
        "1970393557045298?hl=en"
    ),
]


def main():
    extracted_jobs = []

    for url in TEST_URLS:
        print(f"\nScraping: {url}")

        try:
            result = firecrawl.scrape(url, formats=["markdown"])
            data = get_field(result, "data", result)
            markdown = get_field(data, "markdown", "") or ""

            if not markdown:
                print("Skipped: no Markdown returned.")
                continue

            job = extract_job_details(url, markdown)
            extracted_jobs.append(job)

            print("Title:", job.get("title"))
            print("Company:", job.get("company"))
            print("Job type:", job.get("job_type"))
            print("Source job ID:", job.get("source_job_id"))

        except Exception as exc:
            print("Scrape failed:", str(exc)[:300])

    # Keep True for the first run. Change to False only when ready to write.
    DRY_RUN = False

    report = ingest_jobs(
        extracted_jobs,
        dry_run=DRY_RUN,
    )

    print("\n--- INGESTION REPORT ---")

    for key, value in report.items():
        print(f"\n{key}:")
        print(value)

    if DRY_RUN:
        print("\nDRY RUN: no database records were inserted or updated.")
    else:
        print("\nLIVE MODE: check the errors field and verify Supabase.")


if __name__ == "__main__":
    main()
