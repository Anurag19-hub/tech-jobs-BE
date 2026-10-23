
import os
from dotenv import load_dotenv
from firecrawl import Firecrawl

load_dotenv()

api_key = os.getenv("FIRECRAWL_API_KEY")
if not api_key:
    raise RuntimeError("FIRECRAWL_API_KEY is missing")

firecrawl = Firecrawl(api_key=api_key)


def get_field(obj, name, default=None):
    """Read a field from either a dictionary or an SDK object."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


url = (
    "https://careers.ibm.com/en_US/careers/"
    "JobDetail?jobId=137471&source=WEB_Sweng_NA"
)

print("Scraping discovered job page...")
print("URL:", url)

try:
    result = firecrawl.scrape(
        url,
        formats=["markdown", "links"],
    )

    data = get_field(result, "data", result)

    markdown = get_field(data, "markdown", "") or ""
    links = get_field(data, "links", []) or []
    metadata = get_field(data, "metadata", {}) or {}

    print("\n--- PAGE DETAILS ---")
    print("Page title:", get_field(metadata, "title", "Not provided"))
    print("Content length:", len(markdown))
    print("Links extracted:", len(links))

    print("\n--- CONTENT PREVIEW ---")
    print(markdown[:2500] or "No markdown content returned.")

    print("\n--- POSSIBLE APPLICATION LINKS ---")
    for link in links:
        if isinstance(link, str) and any(
            word in link.lower()
            for word in ("apply", "jobdetail", "job-detail")
        ):
            print(link)

except Exception as exc:
    print("Scrape failed:", type(exc).__name__, str(exc))
