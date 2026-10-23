
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.health import router as health_router
from app.routers.companies import router as companies_router
from app.routers.jobs import router as jobs_router
from app.routers.collection import router as collection_router


app = FastAPI(
    title=settings.app_name,
    description="API for the IndiaTechIntelligence platform",
    version="1.0.0",
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(companies_router)
app.include_router(jobs_router)
app.include_router(collection_router)


@app.get("/")
def root():
    return {
        "message": "Welcome to IndiaTechIntelligence API",
        "docs": "/docs",
    }
