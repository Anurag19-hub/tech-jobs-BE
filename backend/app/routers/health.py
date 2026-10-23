
from fastapi import APIRouter
from app.database import supabase

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "IndiaTechIntelligence API",
    }


@router.get("/health/database")
def database_health_check():
    try:
        supabase.table("companies").select("id").limit(1).execute()

        return {
            "status": "healthy",
            "database": "connected",
            "table": "companies",
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(exc),
        }
