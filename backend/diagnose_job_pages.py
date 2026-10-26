from app.services.discovery_service import firecrawl, call_firecrawl, get_field

urls = [
    "https://careers.ibm.com/en_US/careers/JobDetail?jobId=134384&source=WEB_Sweng_NA",
    "https://apply.careers.microsoft.com/careers/job/1970393557045586?hl=en",
]

for url in urls:
    print("\n--- URL:", url, "---")
    result = call_firecrawl(
        lambda: firecrawl.scrape(url, formats=["markdown"])
    )
    data = get_field(result, "data", result)
    markdown = get_field(data, "markdown", "") or ""
    lines = markdown.splitlines()

    for i, line in enumerate(lines):
        keywords = [
            "employment type", "full-time", "full time",
            "internship", "executive referrals only", "job type"
        ]
        if any(word in line.lower() for word in keywords):
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            print("\n".join(lines[start:end]))
