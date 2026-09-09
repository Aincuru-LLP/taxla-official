"""Pytest configuration for the AINCURU × TAXLA backend.

Adds the project root to sys.path so `from app.core.config import settings`
works from the test files. Enables `pytest-asyncio` in auto mode so async
test functions run without per-test `@pytest.mark.asyncio` decorators.
"""
import os
import sys

# Ensure the project root is importable when running `pytest tests/`
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Provide a default JWT_SECRET for tests if the dev hasn't set one.
os.environ.setdefault("JWT_SECRET", "test-only-secret-not-for-production-1234")

# Set ENVIRONMENT=test BEFORE any app.* is imported so that
# app/core/database.py picks NullPool when constructing the async engine.
# This prevents the "Event loop is closed" error that pytest-asyncio's
# per-test event-loop creation would otherwise hit when reusing a module-level
# engine across tests.
os.environ.setdefault("ENVIRONMENT", "test")

import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def _dispose_db_engine():
    """Dispose the app-level async engine after each test so its connection
    pool doesn't straddle pytest-asyncio's per-test event loops."""
    yield
    try:
        from app.core.database import async_engine
        await async_engine.dispose()
    except Exception:
        # Disposal can race with pytest's final teardown; swallow.
        pass