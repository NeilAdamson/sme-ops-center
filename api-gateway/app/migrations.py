"""Migration runner for application startup."""
import logging
from alembic import command
from alembic.config import Config
import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


def wait_for_db(max_retries=30, retry_delay=2):
    """Wait for database to be ready before running migrations."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://smeops:change-me@postgres:5432/smeops"
    )
    
    for attempt in range(max_retries):
        try:
            engine = create_engine(database_url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database is ready")
            return True
        except OperationalError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Database not ready (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay)
            else:
                logger.error(f"Database not ready after {max_retries} attempts")
                raise
    return False


def run_migrations():
    """Run Alembic migrations on application startup."""
    try:
        # Wait for database to be ready
        wait_for_db()
        
        # Get path to alembic.ini
        alembic_cfg = Config(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
        
        # Override sqlalchemy.url with environment variable
        alembic_cfg.set_main_option("sqlalchemy.url", os.getenv(
            "DATABASE_URL",
            "postgresql://smeops:change-me@postgres:5432/smeops"
        ))
        
        logger.info("Running database migrations...")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Failed to run database migrations: {e}")
        raise
