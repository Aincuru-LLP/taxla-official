"""Tests for the Phase 04 validation engine.

Covers three layers:
  * Pure-Python validator regex tests (POSITIVE / NEGATIVE per field).
  * ``ValidationEngine.validate_application_extractions`` confidence branching
    (HIGH / MEDIUM / LOW) plus per-row validation_errors persistence.
  * ``ValidationEngine.override_validation_review`` (the MEDIUM-path reviewer
    override).

Run: pytest backend/tests/test_validation.py -v
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.database import AsyncSessionLocal  # noqa: E402 — NullPool in test mode
from app.models.domain import (  # noqa: E402
    Application,
    Branch,
    Client,
    ExtractedData,
    Workflow,
)
from app.models.domain import Base  # noqa: E402
from app.models.state import ApplicationState  # noqa: E402
from app.services.validators import (  # noqa: E402
    VALIDATION_RULES,
    validate_aadhaar,
    validate_email,
    validate_gstin,
    validate_ifsc,
    validate_mobile,
    validate_pan,
    validate_pincode,
)
from app.services.validation_engine import (  # noqa: E402
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MEDIUM_THRESHOLD,
    ValidationEngine,
    _classify_confidence,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    """Create all tables once per test session (idempotent)."""
    from app.core.database import async_engine
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db():
    """Yield a session that auto-rolls back at the end of each test."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


async def _seed_app_in_state(db: AsyncSession, start_state: str) -> Application:
    """Insert a branch + client + application + workflow with given state."""
    branch = Branch(name="Test Branch", code=f"T{uuid.uuid4().hex[:8].upper()}", status="ACTIVE")
    db.add(branch)
    await db.flush()

    client = Client(
        branch_id=branch.id,
        business_name="Test Co",
        applicant_name="Test Applicant",
        mobile_number="9999999999",
        pan_number=f"ABCDE{uuid.uuid4().hex[:4].upper()}",
        aadhaar_number_hash="0" * 64,
    )
    db.add(client)
    await db.flush()

    app = Application(
        client_id=client.id,
        branch_id=branch.id,
        application_number=f"TEST-{uuid.uuid4().hex[:8].upper()}",
        status=start_state,
    )
    db.add(app)
    await db.flush()

    workflow = Workflow(
        application_id=app.id,
        current_node=start_state,
        status="RUNNING",
        context_json={},
    )
    db.add(workflow)
    await db.flush()
    await db.refresh(app)
    return app


async def _ensure_reviewer_user(db: AsyncSession) -> "User":
    """Return any existing reviewer user, or create one for the test session.

    Needed because ``transition()`` writes an AuditLog row whose
    ``actor_id`` is a FK into ``users.id`` — passing a random UUID causes
    IntegrityError. Re-using a known user keeps the override tests honest.
    """
    from app.models.domain import User
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if user is not None:
        return user
    user = User(
        branch_id=None,
        role="REVIEWER_AUDITOR",
        name="Test Reviewer",
        email=f"reviewer-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="x" * 60,  # bcrypt-shaped dummy; we don't log in here
    )
    db.add(user)
    await db.flush()
    return user


# ---------------------------------------------------------------------------
# Pure-Python regex validators
# ---------------------------------------------------------------------------


class TestValidators:
    """Each validator must reject malformed inputs and accept well-shaped ones."""

    def test_pan_accepts_valid(self):
        assert validate_pan("ABCDE1234F") is True
        assert validate_pan("abcde1234f") is True  # case-insensitive
        assert validate_pan("  ABCDE1234F  ") is True  # whitespace-tolerant

    def test_pan_rejects_invalid(self):
        assert validate_pan("ABCD1234F") is False     # too short
        assert validate_pan("ABCDE12345F") is False   # too long
        assert validate_pan("12345ABCDE") is False    # wrong order
        assert validate_pan("") is False
        assert validate_pan(None) is False

    def test_aadhaar_accepts_valid(self):
        assert validate_aadhaar("123456789012") is True
        assert validate_aadhaar("1234 5678 9012") is True

    def test_aadhaar_rejects_invalid(self):
        assert validate_aadhaar("12345") is False
        assert validate_aadhaar("12345678901") is False  # 11 digits
        assert validate_aadhaar("") is False

    def test_ifsc_accepts_valid(self):
        assert validate_ifsc("HDFC0000123") is True
        assert validate_ifsc("sbin0001234") is True

    def test_ifsc_rejects_invalid(self):
        assert validate_ifsc("HDFC1000123") is False    # 5th char must be '0'
        assert validate_ifsc("HDF00000123") is False    # 3 letters only
        assert validate_ifsc("") is False

    def test_gstin_accepts_valid(self):
        assert validate_gstin("22ABCDE1234F1Z5") is True

    def test_gstin_rejects_invalid(self):
        assert validate_gstin("22ABCDE1234F1A5") is False  # wrong char where 'Z' goes
        assert validate_gstin("") is False

    def test_mobile_accepts_valid(self):
        assert validate_mobile("9876543210") is True
        assert validate_mobile("6123456789") is True

    def test_mobile_rejects_invalid(self):
        assert validate_mobile("5876543210") is False  # starts with 5
        assert validate_mobile("987654321") is False   # 9 digits
        assert validate_mobile("98765432101") is False  # 11 digits

    def test_email_accepts_valid(self):
        assert validate_email("test@example.com") is True
        assert validate_email("user.name+tag@sub.domain.co") is True

    def test_email_rejects_invalid(self):
        assert validate_email("not-an-email") is False
        assert validate_email("@missing-local.com") is False
        assert validate_email("missing-domain@") is False

    def test_pincode_accepts_valid(self):
        assert validate_pincode("110001") is True
        assert validate_pincode("560001") is True

    def test_pincode_rejects_invalid(self):
        # Note: leading-zero PINs ARE legal (e.g. Delhi 011001), so "012345"
        # is valid here — only length and non-digit chars are rejected.
        assert validate_pincode("11000") is False     # 5 digits
        assert validate_pincode("1100011") is False   # 7 digits
        assert validate_pincode("ABC123") is False    # contains letters
        assert validate_pincode("") is False

    def test_validation_rules_map_contains_all_keys(self):
        """All fields Phase 04 promised must be mapped."""
        for k in (
            "pan_number",
            "aadhaar_number",
            "bank_ifsc",
            "gstin",
            "mobile_number",
            "email",
            "pincode",
            "unit_pin",
            "official_pin",
        ):
            assert k in VALIDATION_RULES


# ---------------------------------------------------------------------------
# Confidence branching
# ---------------------------------------------------------------------------


class TestClassifyConfidence:
    def test_high(self):
        assert _classify_confidence(0.85) == "HIGH"
        assert _classify_confidence(0.99) == "HIGH"
        assert _classify_confidence(1.0) == "HIGH"

    def test_medium(self):
        assert _classify_confidence(0.70) == "MEDIUM"
        assert _classify_confidence(0.84) == "MEDIUM"
        assert _classify_confidence(0.75) == "MEDIUM"

    def test_low(self):
        assert _classify_confidence(0.69) == "LOW"
        assert _classify_confidence(0.50) == "LOW"
        assert _classify_confidence(0.0) == "LOW"

    def test_thresholds_constants(self):
        # Phase 04 plan promises these exact thresholds.
        assert CONFIDENCE_HIGH_THRESHOLD == 0.85
        assert CONFIDENCE_MEDIUM_THRESHOLD == 0.70


async def _seed_extractions(
    db: AsyncSession,
    app: Application,
    rows: list[tuple[str, str | None, float]],
) -> list[ExtractedData]:
    """Insert ExtractedData rows for an app.

    Each tuple is (field_name, field_value, final_confidence).
    Returns the inserted rows.
    """
    out: list[ExtractedData] = []
    for field_name, field_value, conf in rows:
        ext = ExtractedData(
            application_id=app.id,
            field_name=field_name,
            field_value=field_value,
            final_confidence=conf,
        )
        db.add(ext)
        out.append(ext)
    await db.flush()
    return out


async def _load_extractions(db: AsyncSession, app_id):
    rows = (
        await db.execute(select(ExtractedData).where(ExtractedData.application_id == app_id))
    ).scalars().all()
    return list(rows)


class TestValidateBranching:
    async def test_high_confidence_transitions_to_nic_review(self, db):
        app = await _seed_app_in_state(db, ApplicationState.VALIDATION.value)
        await _seed_extractions(
            db, app,
            [
                ("pan_number", "ABCDE1234F", 0.95),
                ("mobile_number", "9876543210", 0.90),
            ],
        )
        await db.commit()

        err = await ValidationEngine.validate_application_extractions(app.id, db, actor_id=None)
        assert err is None

        # re-fetch app state
        fresh = (
            await db.execute(select(Application).where(Application.id == app.id))
        ).scalars().one()
        assert fresh.status == ApplicationState.NIC_REVIEW.value

        ext_rows = await _load_extractions(db, app.id)
        for ext in ext_rows:
            assert ext.validation_status == "PASS"
            assert ext.validation_errors in (None, []) or len(ext.validation_errors) == 0

    async def test_medium_confidence_transitions_to_validation_review(self, db):
        app = await _seed_app_in_state(db, ApplicationState.VALIDATION.value)
        # mean = 0.78 -> MEDIUM
        await _seed_extractions(
            db, app,
            [
                ("pan_number", "ABCDE1234F", 0.80),
                ("mobile_number", "9876543210", 0.75),
            ],
        )
        await db.commit()

        err = await ValidationEngine.validate_application_extractions(app.id, db, actor_id=None)
        assert err is None

        fresh = (
            await db.execute(select(Application).where(Application.id == app.id))
        ).scalars().one()
        assert fresh.status == ApplicationState.VALIDATION_REVIEW.value

    async def test_low_confidence_transitions_to_human_review_required(self, db):
        app = await _seed_app_in_state(db, ApplicationState.VALIDATION.value)
        # mean = 0.50 -> LOW
        await _seed_extractions(
            db, app,
            [
                ("pan_number", "ABCDE1234F", 0.55),
                ("mobile_number", "9876543210", 0.45),
            ],
        )
        await db.commit()

        err = await ValidationEngine.validate_application_extractions(app.id, db, actor_id=None)
        assert err is None

        fresh = (
            await db.execute(select(Application).where(Application.id == app.id))
        ).scalars().one()
        assert fresh.status == ApplicationState.HUMAN_REVIEW_REQUIRED.value

    async def test_no_extractions_defaults_to_low(self, db):
        """If the application has zero ExtractedData rows, mean = 0.0 -> LOW."""
        app = await _seed_app_in_state(db, ApplicationState.VALIDATION.value)
        await db.commit()

        err = await ValidationEngine.validate_application_extractions(app.id, db, actor_id=None)
        assert err is None

        fresh = (
            await db.execute(select(Application).where(Application.id == app.id))
        ).scalars().one()
        assert fresh.status == ApplicationState.HUMAN_REVIEW_REQUIRED.value

    async def test_invalid_format_persists_validation_errors(self, db):
        """A malformed PAN must produce a validation_errors row, but the branch
        is still driven by mean confidence (HIGH above)."""
        app = await _seed_app_in_state(db, ApplicationState.VALIDATION.value)
        await _seed_extractions(
            db, app,
            [
                ("pan_number", "NOT-A-PAN", 0.95),
                ("applicant_name", "Rajesh Kumar", 0.90),
            ],
        )
        await db.commit()

        err = await ValidationEngine.validate_application_extractions(app.id, db, actor_id=None)
        assert err is None

        rows = await _load_extractions(db, app.id)
        pan_row = next(r for r in rows if r.field_name == "pan_number")
        assert pan_row.validation_status == "FAIL"
        assert isinstance(pan_row.validation_errors, list)
        assert len(pan_row.validation_errors) == 1
        assert pan_row.validation_errors[0]["validator"] == "validate_pan"

        # applicant_name has no registered validator -> PASS regardless
        name_row = next(r for r in rows if r.field_name == "applicant_name")
        assert name_row.validation_status == "PASS"

        fresh = (
            await db.execute(select(Application).where(Application.id == app.id))
        ).scalars().one()
        # mean confidence here ~ 0.925 -> still HIGH -> NIC_REVIEW (format
        # failure does NOT shift the branch — that's a separate concern)
        assert fresh.status == ApplicationState.NIC_REVIEW.value

    async def test_returns_app_not_found(self, db):
        # random uuid that doesn't exist
        err = await ValidationEngine.validate_application_extractions(uuid.uuid4(), db)
        assert err == "APP_NOT_FOUND"


# ---------------------------------------------------------------------------
# Reviewer override
# ---------------------------------------------------------------------------


class TestOverrideValidationReview:
    async def test_approve_transitions_to_nic_review(self, db):
        app = await _seed_app_in_state(db, ApplicationState.VALIDATION_REVIEW.value)
        actor = await _ensure_reviewer_user(db)
        await db.commit()

        out = await ValidationEngine.override_validation_review(
            app.id, approve=True, actor_id=actor.id, db=db,
        )
        assert out["ok"] is True
        assert out["new_state"] == ApplicationState.NIC_REVIEW.value

        fresh = (
            await db.execute(select(Application).where(Application.id == app.id))
        ).scalars().one()
        assert fresh.status == ApplicationState.NIC_REVIEW.value

    async def test_reject_transitions_to_human_review_required(self, db):
        app = await _seed_app_in_state(db, ApplicationState.VALIDATION_REVIEW.value)
        actor = await _ensure_reviewer_user(db)
        await db.commit()

        out = await ValidationEngine.override_validation_review(
            app.id, approve=False, actor_id=actor.id, db=db,
        )
        assert out["ok"] is True
        assert out["new_state"] == ApplicationState.HUMAN_REVIEW_REQUIRED.value

        fresh = (
            await db.execute(select(Application).where(Application.id == app.id))
        ).scalars().one()
        assert fresh.status == ApplicationState.HUMAN_REVIEW_REQUIRED.value

    async def test_override_from_wrong_state_raises_409(self, db):
        """VALIDATION_REVIEW is the only legal starting state."""
        app = await _seed_app_in_state(db, ApplicationState.NIC_REVIEW.value)
        actor = await _ensure_reviewer_user(db)
        await db.commit()

        with pytest.raises(HTTPException) as exc:
            await ValidationEngine.override_validation_review(
                app.id, approve=True, actor_id=actor.id, db=db,
            )
        assert exc.value.status_code == 409

    async def test_override_returns_app_not_found(self, db):
        actor = await _ensure_reviewer_user(db)
        await db.commit()

        out = await ValidationEngine.override_validation_review(
            uuid.uuid4(), approve=True, actor_id=actor.id, db=db,
        )
        assert out["ok"] is False
        assert out["reason"] == "APP_NOT_FOUND"
