
import os
from dotenv import load_dotenv
from firecrawl import Firecrawl

load_dotenv()

api_key = os.getenv("FIRECRAWL_API_KEY")

if not api_key:
    raise RuntimeError("FIRECRAWL_API_KEY is missing from .env")

firecrawl = Firecrawl(api_key=api_key)

url = "https://www.ibm.com/careers/software-engineering"

print("Crawling:", url)

try:
    result = firecrawl.scrape(
        url,
        formats=["markdown", "links"],
    )

    if isinstance(result, dict):
        data = result.get("data", result)
        if isinstance(data, dict):
            markdown = data.get("markdown", "")
            links = data.get("links", [])
        else:
            markdown = ""
            links = []
    else:
        markdown = getattr(result, "markdown", "") or ""
        links = getattr(result, "links", []) or []

    print("\n--- SCRAPE SUMMARY ---")
    print("Page fetched:", bool(markdown or links))
    print("Markdown characters:", len(markdown))
    print("Links found:", len(links))

    print("\n--- CONTENT PREVIEW ---")
    print(markdown[:1500] or "No markdown content returned.")

    print("\n--- SAMPLE LINKS ---")
    for link in links[:15]:
        print(link)

except Exception as exc:
    print("Scraping failed:", str(exc))
