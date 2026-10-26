
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.database import supabase


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

INDIAN_LOCATIONS = {
    "ahmedabad", "bengaluru", "bangalore", "hyderabad", "pune",
    "mumbai", "gurgaon", "gurugram", "noida", "new delhi", "delhi",
    "chennai", "kolkata", "kochi", "cochin", "jaipur", "lucknow",
    "chandigarh", "indore", "bhopal", "surat", "vadodara",
    "gandhinagar", "rajkot", "nagpur", "coimbatore", "visakhapatnam",
    "vizag", "thiruvananthapuram", "trivandrum", "mysuru", "mysore",
    "mangalore", "mangaluru", "nashik", "patna", "ranchi",
    "bhubaneswar", "dehradun", "guwahati", "faridabad", "ghaziabad",
    "greater noida", "andhra pradesh", "arunachal pradesh", "assam",
    "bihar", "chhattisgarh", "goa", "gujarat", "haryana",
    "himachal pradesh", "jharkhand", "karnataka", "kerala",
    "madhya pradesh", "maharashtra", "manipur", "meghalaya",
    "mizoram", "nagaland", "odisha", "punjab", "rajasthan",
    "sikkim", "tamil nadu", "telangana", "tripura", "uttar pradesh",
    "uttarakhand", "west bengal", "jammu and kashmir", "ladakh",
}


def normalize_name(value: str) -> str:
    """Normalize a company name or job title for matching."""
    return re.sub(r"\s+", " ", value.strip()).casefold()


def infer_country(location: str | None) -> str | None:
    """Infer a country only when a known country name or alias is present."""
    if not isinstance(location, str) or not location.strip():
        return None

    normalized = location.casefold()

    for alias in sorted(COUNTRY_ALIASES, key=len, reverse=True):
        if re.search(
            rf"(?<![a-z]){re.escape(alias)}(?![a-z])",
            normalized,
        ):
            return COUNTRY_ALIASES[alias]

    return None


def validate_india_location(location: str | None) -> list[str]:
    """Accept India or recognized Indian city/state locations only."""
    if not isinstance(location, str) or not location.strip():
        return ["Missing job location; cannot verify that the job is in India"]

    normalized = location.casefold().strip()
    country = infer_country(location)

    if country and country != "India":
        return [f"Non-India location detected: {country}"]

    if country == "India":
        return []

    for place in sorted(INDIAN_LOCATIONS, key=len, reverse=True):
        if re.search(
            rf"(?<![a-z]){re.escape(place)}(?![a-z])",
            normalized,
        ):
            return []

    return [
        "Location does not identify India or a recognized Indian city/state; "
        "manual verification required"
    ]


def company_metadata(company_name: str) -> dict:
    """Return metadata for a supported company."""
    key = company_name.strip().casefold()

    if key not in KNOWN_COMPANIES:
        raise ValueError(
            f"Company '{company_name}' is not in the verified company map."
        )

    return KNOWN_COMPANIES[key]


def validate_job(job: dict) -> list[str]:
    """Validate required fields and India-only location eligibility."""
    errors = []

    for field in ("title", "company", "source_url", "apply_url"):
        value = job.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"Missing required value: {field}")

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
        if company.strip().casefold() not in KNOWN_COMPANIES:
            errors.append(f"Unverified company: {company}")

    description = job.get("description")
    if description is not None and not isinstance(description, str):
        errors.append("description must be text or None")

    errors.extend(validate_india_location(job.get("location")))
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
    """Build a job payload without a database-generated ID."""
    title = job["title"].strip()
    company = company_metadata(job["company"])
    location = job["location"].strip()
    country = infer_country(location) or "India"
    now = datetime.now(timezone.utc).isoformat()

    payload = {
        "company_id": company_id,
        "title": title,
        "normalized_title": normalize_name(title),
        "location": location,
        "country": country,
        "job_type": job.get("job_type"),
        "description": job.get("description"),
        "apply_url": job["apply_url"].strip(),
        "source_name": f"{company['name']} Careers",
        "source_job_id": str(job["source_job_id"]).strip(),
        "is_active": True,
        "last_seen_at": now,
        "updated_at": now,
    }

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


def upsert_company(company_name: str, source_url: str) -> dict:
    """
    Insert a company or update its supplied fields.
    Never send the identity ID back in an UPDATE.
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
        # Update only the fields we intend to change.
        # This preserves other existing columns and omits "id".
        result = (
            supabase.table("companies")
            .update(company_payload)
            .eq("id", existing["id"])
            .execute()
        )
    else:
        # PostgreSQL generates the identity ID.
        result = (
            supabase.table("companies")
            .insert(company_payload)
            .execute()
        )

    if not result.data:
        # A concurrent insert could have created the company after our
        # initial lookup. Re-fetch it rather than attempting an unsafe update.
        current = find_existing_company(normalized_name)
        if current:
            return current
        raise RuntimeError("Company save returned no record.")

    return result.data[0]


def save_job(job: dict, company_id: int) -> str:
    """Insert a new job or update an existing job without updating its ID."""
    company = company_metadata(job["company"])
    source_name = f"{company['name']} Careers"
    source_job_id = str(job["source_job_id"]).strip()

    payload = build_job_payload(job, company_id)
    existing = find_existing_job(source_name, source_job_id)

    if existing:
        # Keep existing values when the new extraction has None or "".
        # Only send intended editable fields; never send existing["id"].
        update_payload = {
            key: value
            for key, value in payload.items()
            if value is not None and value != ""
        }

        result = (
            supabase.table("jobs")
            .update(update_payload)
            .eq("id", existing["id"])
            .execute()
        )

        if not result.data:
            raise RuntimeError("Job update returned no record.")

        return "update"

    # The database generates the identity ID on insertion.
    result = supabase.table("jobs").insert(payload).execute()

    if not result.data:
        # Handle a concurrent insert without attempting to update the ID.
        current = find_existing_job(source_name, source_job_id)
        if current:
            update_payload = {
                key: value
                for key, value in payload.items()
                if value is not None and value != ""
            }
            result = (
                supabase.table("jobs")
                .update(update_payload)
                .eq("id", current["id"])
                .execute()
            )
            if result.data:
                return "update"

        raise RuntimeError("Job insert returned no record.")

    return "insert"


def ingest_jobs(
    jobs: list[dict],
    dry_run: bool = True,
) -> dict:
    """Validate and plan or perform ingestion."""
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

        metadata = company_metadata(job["company"])
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
            existing_job = find_existing_job(source_name, source_job_id)

            action = "update" if existing_job else "insert"
            company_id = existing_company["id"] if existing_company else 0
            payload = build_job_payload(job, company_id)

            report["valid_records"] += 1

            if (
                not existing_company
                and normalized_company not in company_cache
            ):
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
                "country": payload["country"],
                "location": payload["location"],
            })

            if dry_run:
                continue

            company_record = upsert_company(
                job["company"],
                job["source_url"],
            )

            saved_action = save_job(job, company_record["id"])

            report["actions"][-1]["action"] = saved_action
            report["actions"][-1]["company_id"] = company_record["id"]

        except Exception as exc:
            report["errors"].append({
                "index": index,
                "title": job.get("title"),
                "error": str(exc)[:500],
            })

    return report
