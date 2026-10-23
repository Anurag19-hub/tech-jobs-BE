
from app.services.link_discovery import classify_url

test_urls = [
    "https://careers.ibm.com/en_US/careers/JobDetail?jobId=137471",
    "https://www.ibm.com/careers/search?q=software",
    "https://www.ibm.com/careers/software-engineering",
    "https://www.ibm.com/careers/JobAlerts",
    "https://www.ibm.com/careers/culture",
    "https://example.com/jobs/frontend-developer",
]

for url in test_urls:
    print(f"{classify_url(url):24} {url}")
