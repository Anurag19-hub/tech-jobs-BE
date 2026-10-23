
from fastapi import APIRouter, HTTPException, Query
from app.database import supabase

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.get("/")
def get_jobs(
    search: str | None = Query(default=None, min_length=1),
    location: str | None = None,
    job_type: str | None = None,
    experience_level: str | None = None,
    company_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        query = supabase.table("jobs").select("*")
        query = query.eq("is_active", True)

        if search:
            query = query.ilike("title", f"%{search}%")

        if location:
            query = query.ilike("location", f"%{location}%")

        if job_type:
            query = query.eq("job_type", job_type)

        if experience_level:
            query = query.eq("experience_level", experience_level)

        if company_id:
            query = query.eq("company_id", company_id)

        result = (
            query.order("published_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return {
            "count": len(result.data),
            "limit": limit,
            "offset": offset,
            "data": result.data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve jobs from the database.",
        ) from exc


@router.get("/{job_id}")
def get_job(job_id: int):
    try:
        result = (
            supabase.table("jobs")
            .select("*")
            .eq("id", job_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Job not found",
            )

        return result.data[0]

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve job.",
        ) from exc
