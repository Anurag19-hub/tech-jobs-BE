
import re
from urllib.parse import parse_qs, urlparse


GENERIC_TITLES = {
    "single position",
    "job details",
    "job detail",
    "careers",
    "job description",
}

COUNTRY_PATTERN = (
    r"India|United States|USA|United Kingdom|UK|Canada|"
    r"Germany|Australia|Finland|Singapore|Japan|France|"
    r"Netherlands|Ireland|Spain|Italy|Brazil|Mexico"
)

JOB_TYPE_MAP = {
    "internship": "Internship",
    "intern": "Internship",
    "co-op": "Internship",
    "apprentice": "Internship",
    "full-time": "Full-Time",
    "full time": "Full-Time",
    "regular": "Full-Time",
    "permanent": "Full-Time",
    "professional": "Full-Time",
    "early professional": "Full-Time",
    "part-time": "Part-Time",
    "part time": "Part-Time",
    "contract": "Contract",
    "contractor": "Contract",
    "temporary": "Temporary",
    "fixed term": "Contract",
    "fixed-term": "Contract",
}


KNOWN_COMPANY_OVERRIDES = {
    "ibm": "IBM",
    "microsoft": "Microsoft",
    "tcs": "TCS",
    "infosys": "Infosys",
    "wipro": "Wipro",
    "hcl": "HCLTech",
    "hcltech": "HCLTech",
    "techmahindra": "Tech Mahindra",
    "lti": "LTIMindtree",
    "ltimindtree": "LTIMindtree",
    "cognizant": "Cognizant",
    "accenture": "Accenture",
    "capgemini": "Capgemini",
    "google": "Google",
    "amazon": "Amazon",
    "meta": "Meta",
    "apple": "Apple",
    "netflix": "Netflix",
    "flipkart": "Flipkart",
    "swiggy": "Swiggy",
    "zomato": "Zomato",
    "paytm": "Paytm",
    "phonepe": "PhonePe",
    "razorpay": "Razorpay",
    "cred": "CRED",
    "meesho": "Meesho",
    "zerodha": "Zerodha",
    "groww": "Groww",
    "ola": "Ola",
    "uber": "Uber",
    "jio": "Jio",
    "airtel": "Airtel",
    "oracle": "Oracle",
    "cisco": "Cisco",
    "salesforce": "Salesforce",
    "adobe": "Adobe",
    "intel": "Intel",
    "nvidia": "Nvidia",
    "qualcomm": "Qualcomm",
    "amd": "AMD",
    "samsung": "Samsung",
}

ATS_PATH_HOSTS = {
    "greenhouse.io",
    "boards.greenhouse.io",
    "lever.co",
    "jobs.lever.co",
    "ashbyhq.com",
    "jobs.ashbyhq.com",
    "smartrecruiters.com",
    "jobs.smartrecruiters.com",
}

ATS_SUBDOMAIN_SUFFIXES = [
    ".myworkdayjobs.com",
    ".workdayjobs.com",
    ".bamboohr.com",
    ".darwinbox.in",
    ".recruitee.com",
    ".freshteam.com",
    ".breezy.hr",
    ".teamtailor.com",
]


def clean_company_name(slug: str) -> str:
    """Format a company slug into a readable company name."""
    cleaned = re.sub(r"[-_]+", " ", slug.strip()).strip()
    key = cleaned.casefold().replace(" ", "")

    if key in KNOWN_COMPANY_OVERRIDES:
        return KNOWN_COMPANY_OVERRIDES[key]

    # Handle short acronyms
    if len(cleaned) <= 3:
        return cleaned.upper()

    return cleaned.title()


def get_company_from_url(url: str) -> str | None:
    """Dynamically identify the company name from any career URL or ATS link."""
    if not url or not isinstance(url, str):
        return None

    parsed = urlparse(url)
    hostname = parsed.netloc.lower()

    if not hostname:
        return None

    # 1. ATS where company is the path slug (e.g. jobs.lever.co/cred)
    for ats_host in ATS_PATH_HOSTS:
        if hostname == ats_host or hostname.endswith("." + ats_host):
            parts = [p for p in parsed.path.strip("/").split("/") if p]
            if parts and parts[0] not in ("jobs", "careers", "apply", "embed", "v1", "v2"):
                return clean_company_name(parts[0])

    # 2. ATS where company is the subdomain (e.g. swiggy.workdayjobs.com)
    for suffix in ATS_SUBDOMAIN_SUFFIXES:
        if hostname.endswith(suffix):
            prefix = hostname[: -len(suffix)]
            prefix = re.sub(r"\.wd\d+$", "", prefix)
            slug = prefix.split(".")[-1]
            if slug:
                return clean_company_name(slug)

    # 3. Direct company career sites (e.g. careers.flipkart.com, tcs.com)
    clean_host = hostname.split(":")[0]
    clean_host = re.sub(
        r"^(?:www|careers?|jobs?|apply|recruiting?|talent|work|tech|corp)\.",
        "",
        clean_host,
    )
    clean_host = re.sub(
        r"\.(?:com|co\.in|in|org|net|io|tech|co|ai|jobs|dev|app|global)$",
        "",
        clean_host,
    )

    slug = clean_host.split(".")[-1]
    if slug and len(slug) >= 2 and slug not in ("search", "portal", "login"):
        return clean_company_name(slug)

    return None


def extract_source_job_id(url: str) -> str | None:
    """Extract a stable job identifier from the source URL."""

    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    for key in ("jobId", "job_id", "reqId", "reqid", "pid"):
        value = params.get(key, [None])[0]
        if value:
            return value

    patterns = [
        r"/careers/job/([^/?#]+)",
        r"/JobDetail/[^/?#]+/([^/?#]+)",
        r"/(?:jobs?|positions?)/([^/?#]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, parsed.path, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def extract_title(markdown: str) -> str | None:
    """Choose a meaningful page heading instead of a generic heading."""

    headings = re.findall(
        r"^#{1,3}\s+(.+?)\s*$",
        markdown,
        re.MULTILINE,
    )

    for heading in headings:
        title = heading.strip()

        # Remove Markdown formatting if present.
        title = re.sub(r"\*\*(.*?)\*\*", r"\1", title)

        if title.lower() in GENERIC_TITLES:
            continue

        if title.lower().endswith(" | microsoft careers"):
            title = title[: -len(" | microsoft careers")].strip()

        if title.lower() in GENERIC_TITLES:
            continue

        if len(title) <= 180:
            return title

    return None


def extract_apply_url(markdown: str) -> str | None:
    """Find the primary application link."""

    patterns = [
        r"\[Apply now\]\((https?://[^)\s]+)",
        r"\[Apply\]\((https?://[^)\s]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, markdown, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def extract_location(markdown: str, title: str | None) -> str | None:
    """Find a likely location line close to the job title."""

    lines = markdown.splitlines()
    title_index = None

    for index, line in enumerate(lines):
        heading = re.match(r"^#{1,3}\s+(.+?)\s*$", line.strip())

        if heading and heading.group(1).strip() == title:
            title_index = index
            break

    if title_index is None:
        return None

    country_regex = re.compile(
        rf"(?:{COUNTRY_PATTERN})(?=$|[\s,])",
        re.IGNORECASE,
    )

    for line in lines[title_index + 1:title_index + 12]:
        candidate = line.strip()

        if not candidate:
            continue

        if candidate.startswith(("#", "[", "-", "*", "|", "`")):
            continue

        if "](" in candidate or candidate.startswith("http"):
            continue

        # Remove a job type concatenated to the location.
        candidate = re.sub(
            r"(Internship|Full[\s-]*Time|Part[\s-]*Time|"
            r"Contract|Temporary|Permanent)\s*$",
            "",
            candidate,
            flags=re.IGNORECASE,
        ).strip(" ,-|")

        if country_regex.search(candidate) and len(candidate) <= 180:
            return candidate

    return None



def extract_job_type(markdown: str) -> str | None:
    """Extract employment type from explicit fields, title/location area, or title itself."""

    lines = markdown.splitlines()

    # 1. Look for explicit metadata fields (Employment type, Contract type, Position type, Job type)
    type_field_patterns = [
        r"^(?:Employment|Contract|Position|Job|Workplace)\s+type",
        r"^(?:Type\s+of\s+employment|Type\s+of\s+contract)",
    ]

    for line in lines:
        cleaned = line.strip()

        for pattern in type_field_patterns:
            if re.match(pattern, cleaned, re.IGNORECASE):
                value = re.sub(
                    pattern,
                    "",
                    cleaned,
                    flags=re.IGNORECASE,
                ).strip(" :-|*`")

                normalized = re.sub(r"\s+", " ", value).lower()

                if normalized in JOB_TYPE_MAP:
                    return JOB_TYPE_MAP[normalized]

    # 2. Inspect the lines immediately after the job title.
    title = extract_title(markdown)

    if title:
        for index, line in enumerate(lines):
            heading = re.match(
                r"^#{1,3}\s+(.+?)\s*$",
                line.strip(),
            )

            if not heading or heading.group(1).strip() != title:
                continue

            for candidate_line in lines[index + 1 : index + 8]:
                candidate = candidate_line.strip()

                if not candidate:
                    continue

                # Recognize a type joined directly to the location,
                # such as "IndiaInternship" or "IndiaRegular".
                match = re.search(
                    r"(Internship|Intern|Full[\s-]*Time|Part[\s-]*Time|"
                    r"Contract|Temporary|Permanent|Regular)\s*$",
                    candidate,
                    re.IGNORECASE,
                )

                if match:
                    normalized = re.sub(
                        r"[\s-]+",
                        "-",
                        match.group(1).lower(),
                    )

                    if normalized in JOB_TYPE_MAP:
                        return JOB_TYPE_MAP[normalized]

                # Don't keep scanning through the whole job description.
                if candidate.startswith(("#", "[", "-", "*")):
                    break

        # 3. Infer from title if explicitly mentioned (e.g. "Software Engineer - Intern")
        title_lower = title.lower()
        if re.search(r"\b(?:intern|internship|apprentice|co-op)\b", title_lower):
            return "Internship"
        if re.search(r"\b(?:contractor|contract)\b", title_lower):
            return "Contract"

    return None



def extract_description(markdown: str) -> str | None:
    """Remove large embedded payloads and retain readable job content."""

    cleaned_lines = []

    for line in markdown.splitlines():
        stripped = line.strip()

        # Skip huge embedded JSON/configuration payloads.
        if stripped.startswith("`{") or stripped.startswith("{"):
            continue

        if len(stripped) > 20000:
            continue

        # Skip obvious page navigation before the actual description.
        if stripped.lower() in {
            "skip to main content",
            "view all jobs",
            "add to cart",
            "upload your resume",
            "find out how well you match with this job",
        }:
            continue

        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines).strip()

    # Prefer the actual description section when available.
    lines = cleaned.splitlines()
    start_index = None

    for index, line in enumerate(lines):
        normalized = line.strip().strip("*").strip().lower()

        if normalized in {"**overview**", "overview", "introduction"}:
            start_index = index
            break

    if start_index is not None:
        lines = lines[start_index:]

    description = "\n".join(lines).strip()

    # Keep the result bounded; do not save huge page dumps.
    if len(description) > 30000:
        description = description[:30000].rstrip()

    return description or None


def extract_job_details(url: str, markdown: str) -> dict:
    """Extract preliminary job details from a scraped career page."""

    title = extract_title(markdown)
    company = get_company_from_url(url)
    location = extract_location(markdown, title)
    job_type = extract_job_type(markdown)

    apply_url = extract_apply_url(markdown)
    source_job_id = extract_source_job_id(url)
    description = extract_description(markdown)

    return {
        "title": title,
        "company": company,
        "location": location,
        "job_type": job_type,
        "source_job_id": source_job_id,
        "source_url": url,
        "apply_url": apply_url,
        "description": description,
        "is_open_verified": False,
    }
