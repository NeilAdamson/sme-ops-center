from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.migrations import run_migrations
from app.routes import docs, gcs

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="SME Ops-Center API Gateway", version="0.1.0")

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(docs.router)
app.include_router(gcs.router)


@app.on_event("startup")
async def startup_event():
    """Run database migrations and ensure directories exist on startup."""
    logger.info("API Gateway starting up...")
    
    # Ensure uploads and sessions directories exist and are writable
    from pathlib import Path
    uploads_dir = Path("/app/uploads")
    sessions_dir = Path("/app/sessions")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Ensured uploads directory exists: {uploads_dir}")
    
    try:
        run_migrations()
    except Exception as e:
        logger.error(f"Startup migration failed: {e}")
        # Don't fail startup if migrations fail - let it be handled separately
        # In production, you might want to fail fast here


@app.get("/health")
async def health():
    """Health check endpoint with database connectivity check."""
    from app.health import check_database_health
    
    db_healthy = await check_database_health()
    status = "ok" if db_healthy else "degraded"
    
    return {
        "status": status,
        "service": "api-gateway",
        "database": "connected" if db_healthy else "disconnected"
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "SME Ops-Center API Gateway", "version": "0.1.0"}
