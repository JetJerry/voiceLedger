import logging
from typing import Generator, Optional
from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from backend.app.config import settings

logger = logging.getLogger("voiceledger.db")

# SQLAlchemy 2.x engine configuration for PostgreSQL
engine: Engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    echo=False,
)

# Standard sessionmaker bound to the engine
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session per request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health(engine_override: Optional[Engine] = None) -> bool:
    """Execute a simple query to verify database connectivity."""
    target_engine = engine_override or engine
    try:
        with target_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except (SQLAlchemyError, OSError, Exception) as e:
        logger.warning("Database health check probe failed: %s", e)
        return False
