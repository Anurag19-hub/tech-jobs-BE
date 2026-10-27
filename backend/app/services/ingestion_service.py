
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.database import supabase


# Initial verified company mappings.
# We will replace this static mapping with dynamic company discovery later.
KNOWN_COMPANIES = {
    "ibm": {
        "name": "IBM",
        "website": "https://www.ibm.com",
        "careers_url": "https://careers.ibm.com",
    },
    "microsoft": {
        "name": "Microsoft",
        "website": "https://www.microsoft.com",
        "careers_url": "https://careers.microsoft.com",
    },
}

COUNTRY_ALIASES = {
    "india": "India",
    "united states": "United States",
    "usa": "United States",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "canada": "Canada",
    "germany": "Germany",
    "australia": "Australia",
    "singapore": "Singapore",
    "japan": "Japan",
    "france": "France",
    "netherlands": "Netherlands",
    "ireland": "Ireland",
    "brazil": "Brazil",
    "mexico": "Mexico",
}


RESTRICTED_TITLE_PATTERNS = [
    r"\bexecutive\s+referrals?\b",
    r"\breferrals?\s+only\b",
    r"\binternal\s+(?:candidates?|applicants?|employees?|transfers?)\s+only\b",
    r"\bfor\s+internal\s+(?:candidates?|applicants?|employees?)\b",
    r"\bpipeline\s+(?:requisition|req)\b",
    r"\btalent\s+pool\s+only\b",
    r"\bdo\s+not\s+apply\b",
]

INDIAN_LOCATIONS = {
    # Major Tech Cities
    "bangalore", "bengaluru", "hyderabad", "pune", "mumbai", "gurgaon", "gurugram",
    "noida", "delhi", "new delhi", "chennai", "kolkata", "ahmedabad", "kochi",
    "cochin", "trivandrum", "thiruvananthapuram", "chandigarh", "jaipur", "indore",
    "coimbatore", "bhubaneswar", "nagpur", "vadodara", "surat", "visakhapatnam",
    "mysore", "mysuru", "lucknow",
    # States & Territories
    "karnataka", "telangana", "maharashtra", "tamil nadu", "haryana",
    "uttar pradesh", "delhi ncr", "kerala", "gujarat", "west bengal",
    "rajasthan", "madhya pradesh", "punjab", "odisha", "andhra pradesh",
}


def normalize_name(value: str) -> str:
    """Normalize a company name or job title for matching."""
    return re.sub(r"\s+", " ", value.strip()).casefold()


def infer_country(location: str | None) -> str | None:
    """Infer a country from location evidence, supporting Indian cities and states."""
    if not location:
        return None

    normalized = location.casefold()

    # Check for explicit non-India countries first
    for alias in sorted(COUNTRY_ALIASES, key=len, reverse=True):
        if alias != "india" and re.search(
            rf"(?<![a-z]){re.escape(alias)}(?![a-z])",
            normalized,
        ):
            return COUNTRY_ALIASES[alias]

    # Explicit India mention
    if re.search(r"(?<![a-z])india(?![a-z])", normalized):
        return "India"

    # Known Indian cities or states
    for ind_loc in INDIAN_LOCATIONS:
        if re.search(rf"(?<![a-z]){re.escape(ind_loc)}(?![a-z])", normalized):
            return "India"

    return None


def company_metadata(company_name: str, source_url: str = "") -> dict:
    """Return metadata for a company, dynamically generating details if unlisted."""
    key = company_name.strip().casefold()

    if key in KNOWN_COMPANIES:
        return KNOWN_COMPANIES[key]

    website = ""
    careers_url = ""
    if source_url:
        parsed = urlparse(source_url)
        if parsed.scheme and parsed.netloc:
            netloc = parsed.netloc
            main_domain = re.sub(
                r"^(?:apply|careers|jobs|tech|corp)\.",
                "",
                netloc,
                flags=re.IGNORECASE,
            )
            website = f"{parsed.scheme}://{main_domain}"
            careers_url = f"{parsed.scheme}://{netloc}"

    clean_name = company_name.strip()
    return {
        "name": clean_name,
        "website": website or f"https://www.{key}.com",
        "careers_url": careers_url or source_url,
    }


def validate_job(job: dict) -> list[str]:
    """Validate a job against required fields, India eligibility, and restricted listings."""
    errors = []

    for field in ("title", "company", "source_url", "apply_url"):
        value = job.get(field)

        if not isinstance(value, str) or not value.strip():
            errors.append(f"Missing required value: {field}")

    # Exclude clearly restricted listings (referrals only, internal requisitions)
    title = job.get("title")
    if isinstance(title, str) and title.strip():
        for pattern in RESTRICTED_TITLE_PATTERNS:
            if re.search(pattern, title, re.IGNORECASE):
                errors.append(
                    f"Restricted or internal-only listing not eligible for public dashboard: '{title}'"
                )
                break

    for field in ("source_url", "apply_url"):
        value = job.get(field)

        if not isinstance(value, str) or not value.strip():
            continue

        parsed = urlparse(value)

        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{field} must be a valid HTTPS URL")

    source_job_id = job.get("source_job_id")

    if source_job_id is None or not str(source_job_id).strip():
        errors.append(
            "Missing stable source_job_id; cannot safely deduplicate"
        )

    company = job.get("company")
    if isinstance(company, str) and company.strip():
        if len(company.strip()) < 2 or len(company.strip()) > 100:
            errors.append(f"Invalid company name length: '{company}'")

    # India-only validation
    location = job.get("location")
    if not location or not isinstance(location, str) or not location.strip():
        errors.append("Missing location; cannot verify India eligibility")
    else:
        country = infer_country(location)
        if country and country != "India":
            errors.append(f"Job is located outside India ({country}): '{location}'")
        elif not country:
            errors.append(f"Ambiguous or missing India location evidence: '{location}'")

    description = job.get("description")

    if description is not None and not isinstance(description, str):
        errors.append("description must be text or None")

    return errors


def find_existing_company(normalized_name: str) -> dict | None:
    """Find a company by its unique normalized name."""
    result = (
        supabase.table("companies")
        .select("*")
        .eq("normalized_name", normalized_name)
        .limit(1)
        .execute()
    )

    return result.data[0] if result.data else None


def find_existing_job(
    source_name: str,
    source_job_id: str,
) -> dict | None:
    """Find a job using its source and stable source job ID."""
    result = (
        supabase.table("jobs")
        .select("*")
        .eq("source_name", source_name)
        .eq("source_job_id", source_job_id)
        .limit(1)
        .execute()
    )

    return result.data[0] if result.data else None


def build_job_payload(job: dict, company_id: int) -> dict:
    """Build a payload matching the existing Supabase jobs table."""
    title = job["title"].strip()
    company = company_metadata(job["company"], job.get("source_url", ""))

    location = job.get("location")
    country = infer_country(location)
    now = datetime.now(timezone.utc).isoformat()

    payload = {
        "company_id": company_id,
        "title": title,
        "normalized_title": normalize_name(title),
        "location": location.strip() if location else None,
        "job_type": job.get("job_type"),
        "description": job.get("description"),
        "apply_url": job["apply_url"].strip(),
        "source_name": f"{company['name']} Careers",
        "source_job_id": str(job["source_job_id"]).strip(),
        "is_active": True,
        "last_seen_at": now,
        "updated_at": now,
    }

    # Do not overwrite the database's default country with None.
    if country:
        payload["country"] = country

    # Include optional fields only when a reliable value is available.
    for field in (
        "workplace_type",
        "experience_level",
        "salary",
        "currency",
        "published_at",
    ):
        value = job.get(field)

        if value is not None and value != "":
            payload[field] = value

    return payload


def merge_existing_job(existing: dict, new: dict) -> dict:
    """Update supplied values while retaining existing useful data."""
    merged = dict(existing)

    for key, value in new.items():
        if value is not None and value != "":
            merged[key] = value

    return merged


def upsert_company(company_name: str, source_url: str) -> dict:
    """
    Create or update a company using its unique normalized name.
    PostgreSQL generates the identity ID automatically.
    """
    metadata = company_metadata(company_name)
    normalized_name = normalize_name(metadata["name"])

    existing = find_existing_company(normalized_name)

    company_payload = {
        "name": metadata["name"],
        "normalized_name": normalized_name,
        "website": metadata["website"],
        "careers_url": metadata["careers_url"],
        "source_url": source_url,
        "is_active": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if existing:
        # Preserve existing optional data if no replacement was supplied.
        merged = dict(existing)

        for key, value in company_payload.items():
            if value is not None and value != "":
                merged[key] = value

        result = (
            supabase.table("companies")
            .update(merged)
            .eq("id", existing["id"])
            .execute()
        )
    else:
        result = (
            supabase.table("companies")
            .insert(company_payload)
            .execute()
        )

    if not result.data:
        raise RuntimeError("Company save returned no record.")

    return result.data[0]


def save_job(job: dict, company_id: int) -> str:
    """
    Insert a new job or update an existing job.
    Returns 'insert' or 'update'.
    """
    company = company_metadata(job["company"], job.get("source_url", ""))
    source_name = f"{company['name']} Careers"
    source_job_id = str(job["source_job_id"]).strip()

    payload = build_job_payload(job, company_id)

    existing = find_existing_job(source_name, source_job_id)

    if existing:
        merged = merge_existing_job(existing, payload)

        result = (
            supabase.table("jobs")
            .update(merged)
            .eq("source_name", source_name)
            .eq("source_job_id", source_job_id)
            .execute()
        )

        if not result.data:
            raise RuntimeError("Job update returned no record.")

        return "update"

    result = (
        supabase.table("jobs")
        .insert(payload)
        .execute()
    )

    if not result.data:
        raise RuntimeError("Job insert returned no record.")

    return "insert"


def ingest_jobs(
    jobs: list[dict],
    dry_run: bool = True,
) -> dict:
    """
    Validate and plan or perform ingestion.

    dry_run=True:
        Read-only database checks; no inserts or updates.

    dry_run=False:
        Save valid companies and jobs to Supabase.
    """
    report = {
        "mode": "dry-run" if dry_run else "live",
        "records_received": len(jobs),
        "valid_records": 0,
        "companies_to_insert": 0,
        "jobs_to_insert": 0,
        "jobs_to_update": 0,
        "rejected": [],
        "errors": [],
        "actions": [],
    }

    seen_keys = set()
    company_cache = {}

    for index, job in enumerate(jobs):
        errors = validate_job(job)

        if errors:
            report["rejected"].append({
                "index": index,
                "title": job.get("title"),
                "errors": errors,
            })
            continue

        metadata = company_metadata(job["company"], job.get("source_url", ""))
        normalized_company = normalize_name(metadata["name"])
        source_name = f"{metadata['name']} Careers"
        source_job_id = str(job["source_job_id"]).strip()
        dedupe_key = (source_name, source_job_id)

        if dedupe_key in seen_keys:
            report["rejected"].append({
                "index": index,
                "title": job.get("title"),
                "errors": ["Duplicate job in this ingestion batch"],
            })
            continue

        seen_keys.add(dedupe_key)

        try:
            existing_company = find_existing_company(normalized_company)

            if existing_company:
                company_id = existing_company["id"]
            else:
                company_id = None

            payload = build_job_payload(job, company_id or 0)
            existing_job = find_existing_job(
                source_name,
                source_job_id,
            )

            action = "update" if existing_job else "insert"

            report["valid_records"] += 1

            if not existing_company and normalized_company not in company_cache:
                report["companies_to_insert"] += 1
                company_cache[normalized_company] = True

            if action == "insert":
                report["jobs_to_insert"] += 1
            else:
                report["jobs_to_update"] += 1

            report["actions"].append({
                "company": metadata["name"],
                "title": job["title"],
                "source_name": source_name,
                "source_job_id": source_job_id,
                "action": action,
                "country": payload.get("country", "India (database default)"),
                "location": payload.get("location"),
            })

            if dry_run:
                continue

            # Create or reuse the company before saving its job.
            company_record = upsert_company(
                job["company"],
                job["source_url"],
            )

            saved_action = save_job(
                job,
                company_record["id"],
            )

            report["actions"][-1]["action"] = saved_action
            report["actions"][-1]["company_id"] = company_record["id"]

        except Exception as exc:
            report["errors"].append({
                "index": index,
                "title": job.get("title"),
                "error": str(exc)[:500],
            })

    return report
