
from fastapi import APIRouter, HTTPException, Query
from app.database import supabase

router = APIRouter(prefix="/api/v1/companies", tags=["Companies"])


@router.get("/")
def get_companies(
    search: str | None = Query(default=None, min_length=1),
    industry: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        query = supabase.table("companies").select("*")

        query = query.eq("is_active", True)

        if search:
            query = query.ilike("name", f"%{search}%")

        if industry:
            query = query.eq("industry", industry)

        result = (
            query.order("name")
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
            detail="Failed to retrieve companies from the database.",
        ) from exc


@router.get("/{company_id}")
def get_company(company_id: int):
    try:
        result = (
            supabase.table("companies")
            .select("*")
            .eq("id", company_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Company not found",
            )

        return result.data[0]

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve company.",
        ) from exc
