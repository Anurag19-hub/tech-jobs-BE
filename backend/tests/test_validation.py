from app.services.ingestion_service import validate_job, infer_country
from app.services.job_extractor import extract_job_type


def test_job_type_extraction_from_title():
    markdown = "## Software Engineer - Intern\nLocation: Bangalore"
    assert extract_job_type(markdown) == "Internship"


def test_job_type_extraction_from_metadata():
    markdown = "## Software Developer\nContract type: Regular\nBangalore, India"
    assert extract_job_type(markdown) == "Full-Time"


def test_infer_country_india():
    assert infer_country("Bengaluru, Karnataka") == "India"
    assert infer_country("Hyderabad, Telangana, India") == "India"
    assert infer_country("Pune, Maharashtra") == "India"
    assert infer_country("Gurgaon, Haryana") == "India"


def test_infer_country_foreign():
    assert infer_country("Seattle, WA, USA") == "United States"
    assert infer_country("London, United Kingdom") == "United Kingdom"
    assert infer_country("Singapore") == "Singapore"


def test_reject_restricted_listings():
    job = {
        "title": "Job Requisition for Executive Referrals only",
        "company": "IBM",
        "source_url": "https://careers.ibm.com/job/123",
        "apply_url": "https://careers.ibm.com/apply/123",
        "source_job_id": "123",
        "location": "Bangalore, India",
    }
    errors = validate_job(job)
    assert any("Restricted or internal-only" in err for err in errors)


def test_reject_foreign_location():
    job = {
        "title": "Senior Software Engineer",
        "company": "Microsoft",
        "source_url": "https://careers.microsoft.com/job/456",
        "apply_url": "https://careers.microsoft.com/apply/456",
        "source_job_id": "456",
        "location": "Redmond, WA, USA",
    }
    errors = validate_job(job)
    assert any("located outside India" in err for err in errors)


def test_accept_valid_india_job():
    job = {
        "title": "Cloud Solutions Architect",
        "company": "IBM",
        "source_url": "https://careers.ibm.com/job/789",
        "apply_url": "https://careers.ibm.com/apply/789",
        "source_job_id": "789",
        "location": "Bengaluru, Karnataka, India",
    }
    errors = validate_job(job)
    assert errors == []


def test_dynamic_company_extraction():
    from app.services.job_extractor import get_company_from_url

    assert get_company_from_url("https://www.tcs.com/careers/india/software-engineer") == "TCS"
    assert get_company_from_url("https://careers.flipkart.com/jobs/12345") == "Flipkart"
    assert get_company_from_url("https://jobs.lever.co/cred/abc-xyz") == "CRED"
    assert get_company_from_url("https://boards.greenhouse.io/swiggy/jobs/999") == "Swiggy"
    assert get_company_from_url("https://zomato.workdayjobs.com/en-US/careers/job/1") == "Zomato"
    assert get_company_from_url("https://razorpay.com/careers/backend-lead") == "Razorpay"


def test_dynamic_company_validation():
    # Any new Indian startup / company must NOT be rejected as 'Unverified company'
    job = {
        "title": "Full Stack Engineer",
        "company": "Swiggy",
        "source_url": "https://careers.swiggy.com/jobs/101",
        "apply_url": "https://careers.swiggy.com/apply/101",
        "source_job_id": "swiggy-101",
        "location": "Bengaluru, Karnataka",
    }
    errors = validate_job(job)
    assert errors == []

    # Arbitrary new tech company
    startup_job = {
        "title": "DevOps Engineer",
        "company": "NextGen FinTech",
        "source_url": "https://nextgenfintech.io/careers/devops",
        "apply_url": "https://nextgenfintech.io/apply/devops",
        "source_job_id": "ngf-789",
        "location": "Hyderabad, Telangana",
    }
    assert validate_job(startup_job) == []
