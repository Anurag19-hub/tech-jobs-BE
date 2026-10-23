
from dotenv import load_dotenv
from firecrawl import Firecrawl

from app.services.link_discovery import filter_job_links

load_dotenv()

import os

api_key = os.getenv("FIRECRAWL_API_KEY")
if not api_key:
    raise RuntimeError("FIRECRAWL_API_KEY is missing")

firecrawl = Firecrawl(api_key=api_key)

url = "https://www.ibm.com/careers/software-engineering"

print("Fetching career page...")
result = firecrawl.scrape(url, formats=["links"])

if isinstance(result, dict):
    data = result.get("data", result)
    links = data.get("links", []) if isinstance(data, dict) else []
else:
    links = getattr(result, "links", []) or []

candidates = filter_job_links(links)

print(f"\nTotal links extracted: {len(links)}")
print(f"Potential job/career links: {len(candidates)}")

for index, candidate in enumerate(candidates[:25], start=1):
    print(f"{index}. {candidate}")

if not candidates:
    print(
        "\nNo matching links on this page. "
        "The next crawler iteration can inspect sitemaps "
        "and links on other career pages."
    )
