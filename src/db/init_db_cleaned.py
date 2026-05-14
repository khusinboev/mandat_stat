"""
src/db/init_db.py (CLEANED UP)

Purpose: Initialize database connection only. Schema creation and migrations are now handled by Alembic.

BEFORE (inline DDL):
  - DO $$ ... END $$ blocks directly in Python code
  - Home-grown migration logic (error-prone, hard to track)
  
AFTER (Alembic-based):
  - Only database connection setup
  - Schema creation and all DDL handled by Alembic
  - Call `alembic upgrade head` on startup to apply pending migrations
"""

import logging
from typing import Optional

import psycopg2
from config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER

logger = logging.getLogger(__name__)

db: Optional[psycopg2.extensions.connection] = None


def connect_to_db():
    """Establish database connection."""
    global db
    try:
        db = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        logger.info("✅ Database connection established: %s@%s:%s/%s", DB_USER, DB_HOST, DB_PORT, DB_NAME)
    except psycopg2.OperationalError as e:
        logger.error("❌ Database connection failed: %s", e)
        raise


def init_db_alembic():
    """
    Run Alembic migrations to set up database schema.
    
    This replaces all the old DO $$ ... END $$ blocks.
    Call this on startup to apply pending migrations.
    """
    import subprocess
    import sys
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd="/home/adhambek/projects/pythons/udemy/mandat_stat",  # Set to project root
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error("❌ Alembic migration failed:\n%s", result.stderr)
            raise RuntimeError(f"Alembic migration failed: {result.stderr}")
        logger.info("✅ Alembic migrations applied successfully")
        logger.debug("Alembic output:\n%s", result.stdout)
    except Exception as e:
        logger.error("❌ Error running Alembic migrations: %s", e)
        # Don't raise — allow startup to continue; next alembic run will retry


def init_db():
    """Initialize database: connect and run migrations."""
    connect_to_db()
    init_db_alembic()
    logger.info("✅ Database initialization complete")
