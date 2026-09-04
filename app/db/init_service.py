"""Initialization service for Docker Compose 'init' container.

Orchestrates clean startup order by:
1. Waiting for PostgreSQL database to accept connections.
2. Waiting for Redis broker to accept ping commands.
3. Creating all Star Schema tables (DDL).
4. Seeding baseline dimensions (Categorias, Geografia, Tipos de Índice).
5. Exiting with status code 0 so dependent services ('api', 'celery_worker') can start.
"""

import sys
import time
import redis
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.models import Base
from app.db.session import SessionLocal, engine, seed_default_dimensions

setup_logging(settings.LOG_LEVEL)
logger = get_logger("init_service")


def wait_for_postgres(timeout_seconds: int = 60) -> None:
    """Blocks until PostgreSQL responds to connectivity checks."""
    logger.info("Connecting to PostgreSQL at %s...", settings.DATABASE_URL.split("@")[-1])
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("PostgreSQL is healthy and accepting connections.")
            return
        except Exception as exc:
            logger.info("Waiting for PostgreSQL... (%s)", exc)
            time.sleep(2)
    logger.error("Timed out waiting for PostgreSQL after %d seconds.", timeout_seconds)
    sys.exit(1)


def wait_for_redis(timeout_seconds: int = 60) -> None:
    """Blocks until Redis responds to PING."""
    logger.info("Connecting to Redis at %s...", settings.REDIS_URL)
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            client = redis.from_url(settings.REDIS_URL, socket_timeout=2.0)
            if client.ping():
                logger.info("Redis is healthy and accepting connections.")
                return
        except Exception as exc:
            logger.info("Waiting for Redis... (%s)", exc)
            time.sleep(2)
    logger.error("Timed out waiting for Redis after %d seconds.", timeout_seconds)
    sys.exit(1)


def initialize_schema_and_seeds() -> None:
    """Applies Star Schema DDL and seeds baseline dimensions."""
    logger.info("Creating Star Schema database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created successfully.")

    logger.info("Seeding baseline dimensional entities...")
    with SessionLocal() as session:
        seed_default_dimensions(session)
    logger.info("Baseline dimensions seeded successfully.")


def main() -> None:
    """Main entry point for initialization container."""
    logger.info("Starting AutoINCC Initialization Service...")
    wait_for_postgres()
    wait_for_redis()
    initialize_schema_and_seeds()
    logger.info("AutoINCC pre-flight initialization completed successfully. Exiting cleanly (code 0).")
    sys.exit(0)


if __name__ == "__main__":
    main()
