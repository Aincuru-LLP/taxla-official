from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.models.domain import Base

# Async Engine for FastAPI Routes
# Use NullPool when ENVIRONMENT=test so each connection is opened/closed on the
# current event loop — pytest-asyncio creates a fresh loop per test, and a
# pooled engine ends up holding connections bound to a now-closed loop.
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    future=True,
    pool_pre_ping=True,
    poolclass=NullPool if settings.ENVIRONMENT == "test" else None,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Synchronous Engine for Alembic and Background Tasks
sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    echo=(settings.ENVIRONMENT == "development"),
    pool_pre_ping=True
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False
)

async def get_async_db():
    """Yields an async DB session. Routes are responsible for calling commit() explicitly."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
