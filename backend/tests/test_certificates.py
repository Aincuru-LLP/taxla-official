"""Phase 07 — Certificate endpoint tests.

Covers:
  * PDF generator: returns valid PDF bytes (header + EOF), contains the
    application number, idempotent file writes.
  * GET /api/v1/applications/{id}/certificate:
      - 409 with the canonical "Application not yet completed" message
        when the application hasn't reached COMPLETED.
      - 200 with `application/pdf` content-type when the app is COMPLETED
        and the file exists on disk.
      - 403 on cross-branch access.
  * POST /api/v1/applications/{id}/certificate/generate:
      - 200 + file written + Certificate row populated.
      - 403 for OPERATOR (REVIEWER_AUDITOR+ required).
      - 400 if application is in NEW.
"""
from __future__ import annotations

import os
import re
import sys
import uuid
import zlib

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select


def _decompress_pdf_text(body: bytes) -> str:
    """Pull the single FlateDecode content stream out of the placeholder
    PDF and decompress it. Returns the raw content-stream text (the BT...
    ...ET block that draws the certificate). Fails the test loudly if
    the stream can't be located — this means the generator changed shape
    and the test needs to follow.
    """
    match = re.search(rb"stream\n(.*?)\nendstream", body, re.DOTALL)
    assert match is not None, "PDF body has no `stream...endstream`"
    return zlib.decompress(match.group(1)).decode("latin-1")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.main import app  # noqa: E402
from app.models.domain import (  # noqa: E402
    Application,
    Base,
    Branch,
    Certificate,
    Client,
    User,
    Workflow,
)
from app.models.state import ApplicationState  # noqa: E402
from app.services.certificate_generator import (  # noqa: E402
    generate_certificate_pdf,
    render_certificate_pdf,
)


ALL_ROLES = ("OPERATOR", "REVIEWER_AUDITOR", "BRANCH_ADMIN", "SUPER_ADMIN")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    from app.core.database import async_engine
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()


async def _make_branch(db) -> Branch:
    branch = Branch(
        name="Cert Test Branch",
        code=f"CERT{uuid.uuid4().hex[:6].upper()}",
        status="ACTIVE",
    )
    db.add(branch)
    await db.flush()
    return branch


async def _make_user(db, *, role: str, branch_id) -> User:
    user = User(
        branch_id=branch_id,
        role=role,
        name=f"Test {role}",
        email=f"{role.lower()}-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x" * 60,
        status="ACTIVE",
    )
    db.add(user)
    await db.flush()
    return user


async def _make_client(db, *, branch_id) -> Client:
    rand = uuid.uuid4().hex[:4].upper()
    client = Client(
        branch_id=branch_id,
        business_name="Cert Co",
        applicant_name="Cert Applicant",
        mobile_number="9999999999",
        pan_number=f"YY{rand}{uuid.uuid4().hex[:3].upper()}",
        aadhaar_number_hash="0" * 64,
    )
    db.add(client)
    await db.flush()
    return client


async def _make_application(
    db, *, branch_id, client_id, status,
) -> Application:
    application = Application(
        client_id=client_id,
        branch_id=branch_id,
        application_number=f"CERT-{uuid.uuid4().hex[:8].upper()}",
        status=status,
    )
    db.add(application)
    await db.flush()
    db.add(Workflow(
        application_id=application.id,
        current_node=status,
        status="RUNNING",
        context_json={},
    ))
    await db.flush()
    await db.refresh(application)
    return application


@pytest_asyncio.fixture
async def env(db):
    branch_a = await _make_branch(db)
    branch_b = await _make_branch(db)
    client_a = await _make_client(db, branch_id=branch_a.id)
    client_b = await _make_client(db, branch_id=branch_b.id)
    app_new = await _make_application(
        db, branch_id=branch_a.id, client_id=client_a.id,
        status=ApplicationState.NEW.value,
    )
    app_completed = await _make_application(
        db, branch_id=branch_a.id, client_id=client_a.id,
        status=ApplicationState.COMPLETED.value,
    )
    app_other_branch = await _make_application(
        db, branch_id=branch_b.id, client_id=client_b.id,
        status=ApplicationState.COMPLETED.value,
    )

    users = {}
    for role in ALL_ROLES:
        users[role] = await _make_user(db, role=role, branch_id=branch_a.id)
    branch_b_operator = await _make_user(
        db, role="OPERATOR", branch_id=branch_b.id
    )
    await db.commit()

    return {
        "branch_a": branch_a,
        "branch_b": branch_b,
        "app_new": app_new,
        "app_completed": app_completed,
        "app_other_branch": app_other_branch,
        "users": users,
        "branch_b_operator": branch_b_operator,
    }


@pytest_asyncio.fixture
async def client_under_test():
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


def _bearer(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


# ---------------------------------------------------------------------------
# 1. PDF generator — bytes sanity
# ---------------------------------------------------------------------------


class TestPdfGenerator:
    def test_render_returns_valid_pdf_header_and_eof(self):
        body = render_certificate_pdf(
            application_number="UDYAM-2025-0001",
            business_name="Test Bakery",
            applicant_name="Anita Baker",
            pan_number="ABCDE1234F",
            registration_number="UDYAM-UDYAM-2025-0001",
        )
        assert body.startswith(b"%PDF-1.4"), body[:20]
        assert body.rstrip().endswith(b"%%EOF"), body[-20:]

    def test_render_contains_application_number_and_pan(self):
        body = render_certificate_pdf(
            application_number="UDYAM-2025-1234",
            business_name="Hidden Cafe",
            applicant_name="Sam Owner",
            pan_number="ZZZZZ9999A",
            registration_number="UDYAM-UDYAM-2025-1234",
        )
        # The PDF compresses its content stream with FlateDecode, so we
        # decompress it before checking for the values we wrote in.
        content = _decompress_pdf_text(body)
        assert "UDYAM-2025-1234" in content
        assert "ZZZZZ9999A" in content
        assert "Hidden Cafe" in content

    def test_generate_writes_file_to_disk(self, tmp_path):
        out = tmp_path / "cert.pdf"
        path = generate_certificate_pdf(
            application_id="app-1",
            application_number="UDYAM-1",
            business_name="B",
            applicant_name="A",
            pan_number="P",
            registration_number="R",
            output_path=str(out),
        )
        assert os.path.exists(path)
        with open(path, "rb") as f:
            data = f.read()
        assert data.startswith(b"%PDF-1.4")
        assert data.rstrip().endswith(b"%%EOF")

    def test_generate_creates_parent_directory(self, tmp_path):
        nested = tmp_path / "deep" / "nest" / "cert.pdf"
        path = generate_certificate_pdf(
            application_id="app-2",
            application_number="UDYAM-2",
            business_name="B",
            applicant_name="A",
            pan_number="P",
            registration_number="R",
            output_path=str(nested),
        )
        assert os.path.exists(path)


# ---------------------------------------------------------------------------
# 2. GET /certificate — RBAC, state, file presence
# ---------------------------------------------------------------------------


class TestGetCertificate:
    async def test_409_when_application_is_new(
        self, client_under_test, env,
    ):
        operator = env["users"]["OPERATOR"]
        app_new = env["app_new"]
        r = await client_under_test.get(
            f"/api/v1/applications/{app_new.id}/certificate",
            headers=_bearer(operator),
        )
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == "Application not yet completed"

    async def test_409_when_completed_but_file_missing(
        self, client_under_test, env,
    ):
        """Edge case: DB says COMPLETED + has Certificate row, but the
        file on disk was wiped (deploy cleared storage). Same 409.
        """
        operator = env["users"]["OPERATOR"]
        app_obj = env["app_completed"]
        expected_path = os.path.join(
            settings.CERTIFICATES_DIR, f"{app_obj.id}.pdf"
        )
        if os.path.exists(expected_path):
            os.remove(expected_path)
        r = await client_under_test.get(
            f"/api/v1/applications/{app_obj.id}/certificate",
            headers=_bearer(operator),
        )
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == "Application not yet completed"

    async def test_200_when_completed_and_file_exists(
        self, client_under_test, env,
    ):
        """Generate the file first, then GET it."""
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_completed"]
        cert_path = os.path.join(
            settings.CERTIFICATES_DIR, f"{app_obj.id}.pdf"
        )
        os.makedirs(os.path.dirname(cert_path), exist_ok=True)
        generate_certificate_pdf(
            application_id=str(app_obj.id),
            application_number=app_obj.application_number,
            business_name="Cert Co",
            applicant_name="Cert Applicant",
            pan_number="ABCDE1234F",
            registration_number=f"UDYAM-{app_obj.application_number}",
            output_path=cert_path,
        )

        try:
            r = await client_under_test.get(
                f"/api/v1/applications/{app_obj.id}/certificate",
                headers=_bearer(reviewer),
            )
            assert r.status_code == 200, r.text
            assert r.headers["content-type"].startswith("application/pdf")
            assert r.content.startswith(b"%PDF-1.4")
        finally:
            try:
                os.remove(cert_path)
            except OSError:
                pass

    async def test_403_on_cross_branch(
        self, client_under_test, env,
    ):
        # branch_b_operator trying to read branch_a's completed app.
        operator_b = env["branch_b_operator"]
        app_obj = env["app_completed"]  # branch_a
        r = await client_under_test.get(
            f"/api/v1/applications/{app_obj.id}/certificate",
            headers=_bearer(operator_b),
        )
        assert r.status_code == 403, r.text

    async def test_404_on_unknown_application(
        self, client_under_test, env,
    ):
        operator = env["users"]["OPERATOR"]
        r = await client_under_test.get(
            f"/api/v1/applications/{uuid.uuid4()}/certificate",
            headers=_bearer(operator),
        )
        assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# 3. POST /certificate/generate — reviewer+ placeholder writer
# ---------------------------------------------------------------------------


class TestGenerateCertificate:
    async def test_generate_writes_file_and_row(
        self, client_under_test, db, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_new"]
        cert_path = os.path.abspath(os.path.join(
            settings.CERTIFICATES_DIR, f"{app_obj.id}.pdf"
        ))
        # Make sure we start clean.
        if os.path.exists(cert_path):
            os.remove(cert_path)
        try:
            r = await client_under_test.post(
                f"/api/v1/applications/{app_obj.id}/certificate/generate",
                headers=_bearer(reviewer),
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "success"
            assert os.path.exists(body["file_path"])
            # Generator returns absolute paths; compare as such.
            assert os.path.abspath(body["file_path"]) == cert_path

            # Certificate row in DB.
            row = (await db.execute(
                select(Certificate).where(Certificate.application_id == app_obj.id)
            )).scalars().first()
            assert row is not None
            assert os.path.abspath(row.file_path) == cert_path
            assert row.registration_number.startswith("UDYAM-")
        finally:
            try:
                os.remove(cert_path)
            except OSError:
                pass

    async def test_generate_is_idempotent(
        self, client_under_test, env,
    ):
        """Calling generate twice overwrites the file with the same
        content — useful when an admin needs to rebuild after storage loss.
        """
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_new"]
        r1 = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/certificate/generate",
            headers=_bearer(reviewer),
        )
        r2 = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/certificate/generate",
            headers=_bearer(reviewer),
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        try:
            os.remove(r1.json()["file_path"])
        except OSError:
            pass

    async def test_generate_operator_forbidden(
        self, client_under_test, env,
    ):
        operator = env["users"]["OPERATOR"]
        app_obj = env["app_new"]
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/certificate/generate",
            headers=_bearer(operator),
        )
        assert r.status_code == 403

    async def test_generate_cross_branch_forbidden(
        self, client_under_test, env,
    ):
        operator_b = env["branch_b_operator"]
        app_obj = env["app_new"]  # branch_a
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/certificate/generate",
            headers=_bearer(operator_b),
        )
        assert r.status_code == 403

    async def test_generate_404_on_unknown_application(
        self, client_under_test, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        r = await client_under_test.post(
            f"/api/v1/applications/{uuid.uuid4()}/certificate/generate",
            headers=_bearer(reviewer),
        )
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 4. /submit endpoint (Phase 07 hook for SUBMITTED + cert row)
# ---------------------------------------------------------------------------


class TestSubmitEndpoint:
    async def _set_state(self, db, app_obj, status_value):
        """Drive the application into ``status_value`` by mutating
        directly with a paired AuditLog + WorkflowEvent. Tests below
        only need a known starting state for ``/submit``; we don't
        exercise the full state machine here — that's covered by
        ``test_reviews.py``.
        """
        from app.models.domain import AuditLog, WorkflowEvent

        prev = app_obj.status
        app_obj.status = status_value
        workflow = (await db.execute(
            select(Workflow).where(Workflow.application_id == app_obj.id)
        )).scalars().first()
        workflow.current_node = status_value
        audit = AuditLog(
            actor_id=None,
            application_id=app_obj.id,
            action=f"TEST_TRANSITION_{status_value}",
            metadata_json={"from": prev, "to": status_value},
        )
        db.add(audit)
        db.add(WorkflowEvent(
            workflow_id=workflow.id,
            application_id=app_obj.id,
            node_key=status_value,
            event_type="ENTERED",
            status=status_value,
            payload_json={"from_state": prev, "to_state": status_value},
        ))
        await db.commit()

    async def test_submit_populates_certificate_and_transitions(
        self, client_under_test, db, env,
    ):
        """Submit an APPROVED app: APPROVED → SUBMITTING → SUBMITTED,
        with a Certificate row written and the placeholder PDF on disk.
        """
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_new"]
        await self._set_state(db, app_obj, ApplicationState.APPROVED.value)

        cert_path = os.path.join(
            settings.CERTIFICATES_DIR, f"{app_obj.id}.pdf"
        )
        try:
            r = await client_under_test.post(
                f"/api/v1/applications/{app_obj.id}/submit",
                headers=_bearer(reviewer),
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["new_state"] == ApplicationState.SUBMITTED.value

            await db.refresh(app_obj)
            assert app_obj.status == ApplicationState.SUBMITTED.value

            assert os.path.exists(body["certificate_path"])
            row = (await db.execute(
                select(Certificate).where(Certificate.application_id == app_obj.id)
            )).scalars().first()
            assert row is not None
            assert row.file_path == body["certificate_path"]
        finally:
            try:
                os.remove(cert_path)
            except OSError:
                pass

    async def test_submit_400_when_not_approved(
        self, client_under_test, env,
    ):
        reviewer = env["users"]["REVIEWER_AUDITOR"]
        app_obj = env["app_new"]  # status=NEW
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/submit",
            headers=_bearer(reviewer),
        )
        assert r.status_code == 400, r.text

    async def test_submit_operator_forbidden(
        self, client_under_test, env,
    ):
        operator = env["users"]["OPERATOR"]
        app_obj = env["app_new"]
        r = await client_under_test.post(
            f"/api/v1/applications/{app_obj.id}/submit",
            headers=_bearer(operator),
        )
        assert r.status_code == 403