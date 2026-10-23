
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("FIRECRAWL_API_KEY")

if not api_key:
    raise RuntimeError(
        "FIRECRAWL_API_KEY is missing from backend/.env"
    )

query = (
    "India technology companies official websites "
    "careers jobs software developer"
)

print("Searching the web with Firecrawl...")

response = httpx.post(
    "https://api.firecrawl.dev/v2/search",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json={
        "query": query,
        "limit": 5,
    },
    timeout=60.0,
)

if not response.is_success:
    print("Search failed.")
    print("HTTP status:", response.status_code)
    print("Response:", response.text[:1000])
    raise SystemExit(1)

payload = response.json()
data = payload.get("data", payload)

if isinstance(data, dict):
    results = data.get("web", [])
elif isinstance(data, list):
    results = data
else:
    results = []

if not results:
    print("No web results found.")
    print("Response fields:", list(payload.keys()))
else:
    print(f"\nFound {len(results)} candidate pages:\n")

    for index, item in enumerate(results, start=1):
        print(f"{index}. {item.get('title', 'Untitled')}")
        print("   URL:", item.get("url", "No URL returned"))
        print(
            "   Description:",
            item.get("description", "No description returned")[:200],
        )
        print()
