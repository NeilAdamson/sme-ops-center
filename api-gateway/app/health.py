"""Health check implementation for API Gateway."""
from fastapi import HTTPException
from sqlalchemy import text
from app.database import engine
import logging

logger = logging.getLogger(__name__)


async def check_database_health() -> bool:
    """Check if database is accessible."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
