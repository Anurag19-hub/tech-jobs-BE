import os
import re
from dotenv import load_dotenv
from firecrawl import Firecrawl

from app.services.job_extractor import extract_job_details

load_dotenv()

API_KEY = os.getenv("FIRECRAWL_API_KEY")
if not API_KEY:
    raise RuntimeError("FIRECRAWL_API_KEY is missing from backend/.env")

firecrawl = Firecrawl(api_key=API_KEY)


def get_field(obj, name, default=None):
    """Read a field from either a dictionary or an SDK object."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


SAMPLE_PAGES = [
    {
        "company": "IBM",
        "url": (
            "https://careers.ibm.com/en_US/careers/"
            "JobDetail?jobId=137471&source=WEB_Sweng_NA"
        ),
    },
    {
        "company": "Microsoft",
        "url": (
            "https://apply.careers.microsoft.com/careers/job/"
            "1970393557045298?hl=en"
        ),
    },
]


def inspect_page(sample: dict):
    company = sample["company"]
    url = sample["url"]

    print("=" * 80)
    print(f"DIAGNOSING: {company}")
    print(f"URL: {url}")
    print("=" * 80)

    try:
        result = firecrawl.scrape(url, formats=["markdown"])
        data = get_field(result, "data", result)
        markdown = get_field(data, "markdown", "") or ""

        if not markdown:
            print("ERROR: No markdown content returned from Firecrawl.")
            return

        print(f"\n[1] Total Markdown Length: {len(markdown)} characters")

        # 1. Search for employment type keywords in the raw markdown
        print("\n[2] Raw Lines Matching Employment Type / Job Type Keywords:")
        lines = markdown.splitlines()
        found_lines = False
        for i, line in enumerate(lines):
            lower = line.strip().lower()
            if any(term in lower for term in ("employment", "job type", "workplace", "full-time", "full time", "part-time", "internship", "contract")):
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                for j in range(start, end):
                    print(f"   Line {j:4d}: {lines[j]!r}")
                print("   ---")
                found_lines = True

        if not found_lines:
            print("   (No obvious employment keywords found in lines)")

        # 2. Check the first 25 non-empty lines for metadata layout
        print("\n[3] First 25 Content Lines (Header & Metadata Area):")
        printed = 0
        for i, line in enumerate(lines):
            if line.strip():
                print(f"   Line {i:4d}: {line}")
                printed += 1
            if printed >= 25:
                break

        # 3. Run extract_job_details and show current output
        print("\n[4] Output of extract_job_details():")
        extracted = extract_job_details(url, markdown)
        for k, v in extracted.items():
            if k == "description" and v:
                print(f"   {k}: {len(v)} characters (Starts with: {v[:80]!r}...)")
            else:
                print(f"   {k}: {v}")

    except Exception as exc:
        print(f"Failed to inspect {company}: {type(exc).__name__}: {exc}")


def main():
    for sample in SAMPLE_PAGES:
        inspect_page(sample)
        print("\n\n")


if __name__ == "__main__":
    main()
