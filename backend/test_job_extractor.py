
import os
from dotenv import load_dotenv
from firecrawl import Firecrawl

from app.services.job_extractor import extract_job_details

load_dotenv()

api_key = os.getenv("FIRECRAWL_API_KEY")
if not api_key:
    raise RuntimeError("FIRECRAWL_API_KEY is missing")

firecrawl = Firecrawl(api_key=api_key)

url = (
    "https://careers.ibm.com/en_US/careers/"
    "JobDetail?jobId=137471&source=WEB_Sweng_NA"
)

print("Fetching job page...")

result = firecrawl.scrape(url, formats=["markdown"])


def get_field(obj, name, default=None):
    """Read a field from either a dictionary or an SDK object."""
    if isinstance(obj, dict):
        return obj.get(name, default)

    return getattr(obj, name, default)


# Extract Markdown from the Firecrawl response
data = get_field(result, "data", result)
markdown = get_field(data, "markdown", "") or ""

if not markdown:
    raise RuntimeError("No page content was returned by Firecrawl")


# DEBUG: Print the actual Markdown around the job title
print("\n--- DEBUG: MARKDOWN AROUND JOB TITLE ---")

lines = markdown.splitlines()

for i, line in enumerate(lines):
    if "IBM Research/Research Software" in line:
        start = max(0, i - 3)
        end = min(len(lines), i + 15)

        for j in range(start, end):
            print(f"{j}: {lines[j]!r}")

        break
else:
    print("Job title heading not found in Markdown.")


# Run the job extractor
job = extract_job_details(url, markdown)


# Display extracted job details
print("\n--- EXTRACTED JOB ---")

for key, value in job.items():
    if key == "description" and value:
        print(f"{key}: {len(value)} characters")
    else:
        print(f"{key}: {value}")
