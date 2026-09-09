import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, Numeric, BigInteger, Integer,
    TIMESTAMP, ForeignKey, CheckConstraint, JSON, UUID, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


def _utc_now() -> datetime:
    """Timezone-aware UTC now. Replaces datetime.utcnow() (deprecated in 3.12+)."""
    return datetime.now(timezone.utc)

class Branch(Base):
    __tablename__ = "branches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    address = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE")
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)

    users = relationship("User", back_populates="branch")
    clients = relationship("Client", back_populates="branch")
    applications = relationship("Application", back_populates="branch")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    role = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="ACTIVE")
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)

    branch = relationship("Branch", back_populates="users")
    assigned_applications = relationship("Application", back_populates="assigned_user")


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    business_name = Column(String(255), nullable=False)
    applicant_name = Column(String(255), nullable=False)
    mobile_number = Column(String(20), nullable=False)
    email = Column(String(255), nullable=True)
    pan_number = Column(String(10), nullable=False)
    aadhaar_number_hash = Column(String(64), nullable=False)
    
    # New Fields V2
    gender = Column(String(50), nullable=True)
    social_category = Column(String(50), nullable=True)
    divyang_status = Column(Boolean, nullable=True, default=False)
    
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)

    branch = relationship("Branch", back_populates="clients")
    applications = relationship("Application", back_populates="client")


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    application_number = Column(String(100), unique=True, nullable=False)
    workflow_type = Column(String(100), nullable=False, default="NEW_UDYAM")
    status = Column(String(50), nullable=False, default="NEW")
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    enterprise_type = Column(String(50), nullable=True) # Micro, Small, Medium
    social_category = Column(String(50), nullable=True) # Enterprise category
    
    # Bank Details
    bank_name = Column(String(255), nullable=True)
    bank_account_number = Column(String(50), nullable=True)
    bank_ifsc = Column(String(11), nullable=True)
    
    # Legacy Status
    previous_em_ii_uam = Column(String(50), nullable=True) # N/A, EM-II, Previous UAM
    uam_number = Column(String(100), nullable=True)
    
    # Business Status
    incorporation_date = Column(TIMESTAMP(timezone=True), nullable=True)
    business_commenced = Column(Boolean, nullable=True)
    commencement_date = Column(TIMESTAMP(timezone=True), nullable=True)
    major_activity = Column(String(100), nullable=True) # Manufacturing, Services, Trading
    
    # Employment
    male_employees = Column(Integer, nullable=True, default=0)
    female_employees = Column(Integer, nullable=True, default=0)
    other_employees = Column(Integer, nullable=True, default=0)
    child_labour_declaration = Column(Boolean, nullable=False, default=False)
    
    # Financials (New Limits)
    written_down_value = Column(Numeric(15, 2), nullable=True)
    eligible_exclusions = Column(Numeric(15, 2), nullable=True)
    net_investment = Column(Numeric(15, 2), nullable=True)
    total_turnover = Column(Numeric(15, 2), nullable=True)
    export_turnover = Column(Numeric(15, 2), nullable=True)
    net_turnover = Column(Numeric(15, 2), nullable=True)
    
    # Optional Government Services
    interested_in_gem = Column(Boolean, nullable=True, default=False)
    interested_in_treds = Column(Boolean, nullable=True, default=False)
    interested_in_ncs = Column(Boolean, nullable=True, default=False)
    interested_in_nsic_b2b = Column(Boolean, nullable=True, default=False)
    interested_in_in_domain = Column(Boolean, nullable=True, default=False)
    
    # Administration
    district_industries_centre = Column(String(255), nullable=True)
    completion_percentage = Column(Numeric(5, 2), nullable=False, default=0.0)
    
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)

    client = relationship("Client", back_populates="applications")
    branch = relationship("Branch", back_populates="applications")
    assigned_user = relationship("User", back_populates="assigned_applications")
    documents = relationship("Document", back_populates="application", cascade="all, delete-orphan")
    extracted_data = relationship("ExtractedData", back_populates="application", cascade="all, delete-orphan")
    nic_suggestions = relationship("NICSuggestion", back_populates="application", cascade="all, delete-orphan")
    workflow = relationship("Workflow", back_populates="application", uselist=False, cascade="all, delete-orphan")
    portal_sessions = relationship("PortalSession", back_populates="application", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="application", cascade="all, delete-orphan")
    certificate = relationship("Certificate", back_populates="application", uselist=False, cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="application")
    
    # New Relationships
    units = relationship("ApplicationUnit", back_populates="application", cascade="all, delete-orphan")
    official_address = relationship("OfficialAddress", back_populates="application", uselist=False, cascade="all, delete-orphan")
    requirements = relationship("ApplicationRequirement", back_populates="application", cascade="all, delete-orphan", order_by="ApplicationRequirement.sort_order")
    intake_responses = relationship("ApplicationResponse", back_populates="application", cascade="all, delete-orphan", order_by="ApplicationResponse.created_at")
    generated_documents = relationship("GeneratedDocument", back_populates="application", cascade="all, delete-orphan", order_by="GeneratedDocument.created_at.desc()")
    executions = relationship("WorkflowExecution", back_populates="application", cascade="all, delete-orphan", order_by="WorkflowExecution.started_at.desc()")
    checkpoints = relationship("HumanCheckpoint", back_populates="application", cascade="all, delete-orphan", order_by="HumanCheckpoint.created_at.desc()")


class ApplicationUnit(Base):
    __tablename__ = "application_units"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    unit_name = Column(String(255), nullable=False)
    flat = Column(String(255), nullable=True)
    building = Column(String(255), nullable=True)
    village_town = Column(String(255), nullable=True)
    block = Column(String(255), nullable=True)
    road_street = Column(String(255), nullable=True)
    city = Column(String(255), nullable=True)
    pin = Column(String(20), nullable=True)
    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)
    
    application = relationship("Application", back_populates="units")


class OfficialAddress(Base):
    __tablename__ = "official_addresses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False)
    flat = Column(String(255), nullable=True)
    building = Column(String(255), nullable=True)
    village_town = Column(String(255), nullable=True)
    block = Column(String(255), nullable=True)
    road_street = Column(String(255), nullable=True)
    city = Column(String(255), nullable=True)
    pin = Column(String(20), nullable=True)
    state = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)
    
    application = relationship("Application", back_populates="official_address")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)
    storage_path = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    ocr_status = Column(String(50), nullable=False, default="PENDING")
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    application = relationship("Application", back_populates="documents")


class ExtractedData(Base):
    __tablename__ = "extracted_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True)
    field_name = Column(String(100), nullable=False)
    field_value = Column(Text, nullable=True)

    # `confidence` is deprecated as a single aggregate. It is populated with
    # `final_confidence` going forward but kept for backward compatibility
    # with older queries / dashboards. Prefer `final_confidence` in new code.
    confidence = Column(Numeric(4, 3), nullable=True)

    # Phase 02 follow-up: separate confidence signals + processing provenance.
    ocr_confidence = Column(Numeric(4, 3), nullable=True, comment="Tesseract confidence for the OCR line matched to this field (0-1).")
    extraction_confidence = Column(Numeric(4, 3), nullable=True, comment="LLM-extraction confidence (0-1). Heuristic from retry count.")
    final_confidence = Column(Numeric(4, 3), nullable=True, comment="Weighted combination of ocr_confidence + extraction_confidence + validation_status.")
    review_decision = Column(String(50), nullable=True, comment="PASS | REVIEW | FAIL — set by ReviewDecisionService.")

    extraction_model = Column(String(100), nullable=True, comment="Ollama model id (e.g. qwen2.5:3b) used for extraction.")
    extraction_prompt_version = Column(String(50), nullable=True, comment="Bumped when the prompt template changes.")
    schema_version = Column(String(50), nullable=True, comment="Bumped when ExtractionResult schema changes.")

    validation_status = Column(String(50), nullable=False, default="UNVERIFIED")
    validation_errors = Column(JSON, nullable=True, comment="Phase 04: per-field format-error list (list of {validator, message}).")
    bounding_box_json = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    application = relationship("Application", back_populates="extracted_data")


class RawOcrResult(Base):
    """Durable OCR artifact per (document, page).

    Written after every OCR run by the worker so:
      * the OCR text can be inspected / re-fed to extraction without re-running Tesseract,
      * OCR vs extraction regressions can be debugged from history,
      * OCR engines / preprocessing versions are comparable over time.

    Populated by worker/ocr_worker.py. Read by debug tools and by any future
    extraction re-run job.
    """
    __tablename__ = "raw_ocr_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False, default=1)
    raw_text = Column(Text, nullable=False)
    line_count = Column(Integer, nullable=False, default=0)
    average_confidence = Column(Numeric(4, 3), nullable=True, comment="Average Tesseract confidence across all words on the page (0-1).")

    ocr_engine = Column(String(50), nullable=False, comment="e.g. tesseract, paddleocr.")
    ocr_engine_version = Column(String(50), nullable=True, comment="e.g. 5.13.0.")
    preprocessing_version = Column(String(50), nullable=True, comment="Pipeline-internal version string for the preprocessing step.")
    processing_version = Column(String(50), nullable=True, comment="Overall pipeline version (engine + preprocessing).")

    bounding_boxes = Column(JSON, nullable=True, comment="Array of {text, confidence, bbox} per OCR line — same shape as OcrLine.to_dict().")
    language_packs = Column(JSON, nullable=True, comment="e.g. ['eng', 'hin'].")
    metadata_json = Column(JSON, nullable=True, comment="Free-form: dpi, page dimensions, processing time, etc.")

    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    document = relationship("Document", backref="raw_ocr_results")


class NICSuggestion(Base):
    __tablename__ = "nic_suggestions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    nic_code_2digit = Column(String(2), nullable=False)
    nic_code_4digit = Column(String(4), nullable=False)
    nic_code_5digit = Column(String(5), nullable=False)
    description = Column(Text, nullable=False)
    confidence = Column(Numeric(4, 3), nullable=False)
    rationale = Column(Text, nullable=True)
    approved = Column(Boolean, default=False)
    selected_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    application = relationship("Application", back_populates="nic_suggestions")


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False)
    definition_version = Column(String(20), nullable=False, default="1.0")
    current_node = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="RUNNING")
    context_json = Column(JSON, nullable=False, default={})
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)

    application = relationship("Application", back_populates="workflow")
    events = relationship("WorkflowEvent", back_populates="workflow", cascade="all, delete-orphan")


class WorkflowEvent(Base):
    __tablename__ = "workflow_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False)
    node_key = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    payload_json = Column(JSON, nullable=True)
    error_code = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    workflow = relationship("Workflow", back_populates="events")


class PortalSession(Base):
    __tablename__ = "portal_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    portal_name = Column(String(100), nullable=False, default="MOCK_UDYAM_PORTAL")
    session_status = Column(String(50), nullable=False, default="INITIALIZED")
    last_checkpoint = Column(String(100), nullable=True)
    screenshot_path = Column(Text, nullable=True)
    error_log = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)

    application = relationship("Application", back_populates="portal_sessions")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    review_stage = Column(String(50), nullable=False)
    decision = Column(String(50), nullable=False)
    comments = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    application = relationship("Application", back_populates="reviews")


class NicReview(Base):
    """Phase 07 — reviewer decision on a NIC_REVIEW application.

    The state machine transitions capture the lifecycle; this row captures
    the *reasoning* (which codes were chosen, why) for audit + reproducibility.

    ``selected_codes`` is the list of 5-digit NIC codes the reviewer picked
    (multiple if the applicant has multiple activities). For OVERRIDE
    decisions, the chosen 5-digit code is repeated here for searchability.
    """

    __tablename__ = "nic_reviews"
    __table_args__ = (
        CheckConstraint(
            "decision in ('APPROVE','REJECT','OVERRIDE')",
            name="nic_reviews_decision_check",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    selected_codes = Column(JSON, nullable=False, default=list, comment="5-digit NIC codes the reviewer chose.")
    justification = Column(Text, nullable=False)
    decision = Column(String(20), nullable=False, comment="APPROVE | REJECT | OVERRIDE")
    decided_at = Column(TIMESTAMP(timezone=True), nullable=False, default=_utc_now)

    application = relationship("Application", backref="nic_reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class FinalReview(Base):
    """Phase 07 — reviewer signoff before portal submission.

    Captures KYC confirmation, the signoff method (digital signature vs
    Aadhaar OTP), and free-form remarks. One row per application — the
    latest final review is the authoritative signoff.
    """

    __tablename__ = "final_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    kyc_confirmed = Column(Boolean, nullable=False, default=False)
    signoff_method = Column(String(50), nullable=False, comment="DIGITAL_SIGNATURE | AADHAAR_OTP")
    remarks = Column(Text, nullable=True)
    declared_at = Column(TIMESTAMP(timezone=True), nullable=False, default=_utc_now)

    application = relationship("Application", backref="final_reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), unique=True, nullable=False)
    registration_number = Column(String(100), unique=True, nullable=False)
    file_path = Column(Text, nullable=False)
    issued_at = Column(TIMESTAMP(timezone=True), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    application = relationship("Application", back_populates="certificate")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=True)
    action = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=False, default={})
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    application = relationship("Application", back_populates="audit_logs")


# ---------------------------------------------------------------------------
# Phase 08 — Trigger-Action System
# ---------------------------------------------------------------------------


class Trigger(Base):
    """A rule that matches an event and executes a list of actions.

    ``event_pattern`` is either a literal event name (``DOCUMENT_UPLOADED``)
    or a glob (``STATE_TRANSITIONED.*.NIC_REVIEW``). ``condition_json`` is an
    optional dict of key/value constraints applied to the event payload —
    every key in the dict must equal the corresponding field on the event.

    Triggers are scoped per-branch so a tenant can't accidentally trigger
    another tenant's actions. ``last_run_json`` records the most recent
    dispatch outcome for the dashboard; on-match updates are best-effort.
    """
    __tablename__ = "triggers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    event_pattern = Column(String(255), nullable=False)
    condition_json = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    last_run_json = Column(JSON, nullable=True, comment="Last dispatch outcome: {at, matched, executed, error}.")
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)

    actions = relationship(
        "Action",
        back_populates="trigger",
        cascade="all, delete-orphan",
        order_by="Action.sort_order",
    )
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        # Index for the dispatcher's "active triggers for this branch" query.
        Index("ix_triggers_branch_active", "branch_id", "is_active"),
    )


class Action(Base):
    """One execution step attached to a trigger.

    ``type`` selects the runner branch in ``action_runner.execute_action``.
    ``config_json`` holds the type-specific configuration (URL for webhooks,
    email to/subject/body for EMAIL, ``to_state`` for STATE_TRANSITION, etc).
    ``sort_order`` preserves user-defined ordering; ties broken by id.
    """
    __tablename__ = "actions"
    __table_args__ = (
        CheckConstraint(
            "type in ('HTTP_WEBHOOK','EMAIL','SHELL','STATE_TRANSITION','PLAYWRIGHT')",
            name="actions_type_check",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trigger_id = Column(UUID(as_uuid=True), ForeignKey("triggers.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)
    config_json = Column(JSON, nullable=False, default=dict)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    trigger = relationship("Trigger", back_populates="actions")


class EmailOutbox(Base):
    """Stub for outbound emails — Phase 12 will wire SMTP/SendGrid delivery.

    Triggers with ``EMAIL`` actions insert rows here with ``status='queued'``.
    A Phase 12 worker will pick rows up and ship them. Until then the rows
    exist as the audit trail of "who got notified about what".
    """
    __tablename__ = "email_outbox"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','sent','failed')",
            name="email_outbox_status_check",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    to_address = Column(String(255), nullable=False)
    subject = Column(String(998), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    related_application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True)
    related_trigger_id = Column(UUID(as_uuid=True), ForeignKey("triggers.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    sent_at = Column(TIMESTAMP(timezone=True), nullable=True)
    error = Column(Text, nullable=True)


class Webhook(Base):
    """Phase 12 — External Webhook subscription.

    One row per URL the branch wants to be notified about on every
    event the state machine emits. ``subscribed_events`` is a JSON
    list of ``fnmatch``-style patterns (e.g. ``["STATE_TRANSITIONED.*.*",
    "DOCUMENT_UPLOADED"]``); an empty list means "subscribe to all".

    ``secret`` is the HMAC-SHA256 key the receiver must use to verify
    ``X-Taxla-Signature`` — we mint it once at create-time, return it
    in the create response, and never surface it again.

    Branch-scoped so a tenant cannot trigger another tenant's webhooks.
    """
    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    secret = Column(String(64), nullable=False)
    subscribed_events = Column(JSON, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    # Last-delivery bookkeeping — drives the "this webhook looks dead"
    # warning in the UI without forcing the operator to scroll the log.
    last_triggered_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_status = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    deliveries = relationship(
        "WebhookDelivery",
        back_populates="webhook",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class WebhookDelivery(Base):
    """Phase 12 — One row per delivery attempt.

    The dispatcher inserts a row on every attempt (success or failure)
    with the receiver's status code and response body. Operators read
    this to debug "why didn't my callback fire". Cascade-deletes with
    the parent webhook so deleting a subscription also clears its log.
    """
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id = Column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The dispatcher's own event id (from ``event_id`` on the wire) so a
    # delivery row is traceable back to the message that produced it.
    event_id = Column(UUID(as_uuid=True), nullable=True)
    event_name = Column(String(255), nullable=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    attempted_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    error = Column(Text, nullable=True)

    webhook = relationship("Webhook", back_populates="deliveries")


# ---------------------------------------------------------------------------
# Phase 15 / Integration — Document Intelligence & Requirement Engine Models
# ---------------------------------------------------------------------------


class ApplicationRequirement(Base):
    """Canonical requirement item per application (27 Standard Requirements)."""
    __tablename__ = "application_requirements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_key = Column(String(100), nullable=False)
    display_label = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False, default="GENERAL")
    is_required = Column(Boolean, nullable=False, default=True)
    is_completed = Column(Boolean, nullable=False, default=False)
    source = Column(String(50), nullable=True)  # USER_PROVIDED, DOCUMENT_EXTRACTED, AI_DERIVED, HUMAN_CORRECTED, SYSTEM_CALCULATED
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    value = Column(Text, nullable=True)
    validation_error = Column(Text, nullable=True)
    validation_status = Column(String(50), nullable=False, default="UNVERIFIED")  # VALID, INVALID, UNVERIFIED, CONFLICT, STALE
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)

    application = relationship("Application", back_populates="requirements")
    source_document = relationship("Document")


class ApplicationResponse(Base):
    """Client conversational intake responses."""
    __tablename__ = "application_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    question_key = Column(String(100), nullable=False)
    raw_response = Column(Text, nullable=False)
    validated_value = Column(Text, nullable=True)
    channel = Column(String(50), nullable=False, default="AI_CHAT")  # AI_CHAT, FORM, RETURNED_DOCUMENT
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    application = relationship("Application", back_populates="intake_responses")


class Template(Base):
    """Specification metadata for client requirement templates."""
    __tablename__ = "templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(100), unique=True, nullable=False)  # e.g. UDYAM_REQUIREMENT_V1
    name = Column(String(255), nullable=False)
    workflow_type = Column(String(100), nullable=False, default="NEW_UDYAM")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    versions = relationship("TemplateVersion", back_populates="template", cascade="all, delete-orphan")


class TemplateVersion(Base):
    """Immutable versioned structure definition of a template."""
    __tablename__ = "template_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False, default=1)
    structure_json = Column(JSON, nullable=False)  # 9-section definition & fields
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)

    template = relationship("Template", back_populates="versions")
    generated_documents = relationship("GeneratedDocument", back_populates="template_version")


class GeneratedDocument(Base):
    """Generated PDF / DOCX requirement artifacts attached to an application."""
    __tablename__ = "generated_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    template_version_id = Column(UUID(as_uuid=True), ForeignKey("template_versions.id", ondelete="SET NULL"), nullable=True)
    document_title = Column(String(255), nullable=False)
    format = Column(String(20), nullable=False)  # PDF, DOCX
    storage_path = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="GENERATED")  # GENERATING, GENERATED, SENT, RETURNED, INGESTED, ARCHIVED, FAILED
    generated_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)

    application = relationship("Application", back_populates="generated_documents")
    template_version = relationship("TemplateVersion", back_populates="generated_documents")


# ---------------------------------------------------------------------------
# Autonomous Automation & Workflow Visualizer Models
# ---------------------------------------------------------------------------


class WorkflowExecution(Base):
    """Authoritative execution instance for an application workflow run."""
    __tablename__ = "workflow_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_version = Column(String(50), nullable=False, default="2.0")
    status = Column(String(50), nullable=False, default="RUNNING", index=True)  # WAITING, RUNNING, PAUSED, HUMAN_REQUIRED, COMPLETED, FAILED, CANCELLED
    current_node_id = Column(String(100), nullable=False, default="doc_received")
    started_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    duration_seconds = Column(Numeric(10, 2), nullable=True)
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    trigger_source = Column(String(100), nullable=False, default="DOCUMENT_UPLOAD")
    context_json = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)

    application = relationship("Application", back_populates="executions")
    node_executions = relationship(
        "WorkflowNodeExecution",
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="WorkflowNodeExecution.created_at"
    )
    checkpoints = relationship(
        "HumanCheckpoint",
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="HumanCheckpoint.created_at"
    )


class WorkflowNodeExecution(Base):
    """Execution state and telemetry for an individual workflow node."""
    __tablename__ = "workflow_node_executions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(String(100), nullable=False, index=True)
    node_label = Column(String(255), nullable=False)
    node_type = Column(String(50), nullable=False, default="SYSTEM")  # DOCUMENT, PARSER, OCR, AI, VALIDATION, DECISION, PORTAL, HUMAN, RESULT
    status = Column(String(50), nullable=False, default="WAITING", index=True)  # WAITING, QUEUED, RUNNING, SUCCESS, FAILED, PAUSED, HUMAN_REQUIRED, SKIPPED, CANCELLED
    attempt = Column(Integer, nullable=False, default=1)
    max_attempts = Column(Integer, nullable=False, default=3)
    worker_id = Column(String(100), nullable=True)
    input_summary = Column(JSON, nullable=True)
    output_summary = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    logs_text = Column(Text, nullable=True)
    screenshot_path = Column(Text, nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    duration_seconds = Column(Numeric(10, 2), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    updated_at = Column(TIMESTAMP(timezone=True), default=_utc_now, onupdate=_utc_now)

    execution = relationship("WorkflowExecution", back_populates="node_executions")
    checkpoints = relationship("HumanCheckpoint", back_populates="node_execution")


class HumanCheckpoint(Base):
    """Generic Human Checkpoint requiring operator action to resume automation."""
    __tablename__ = "human_checkpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    node_execution_id = Column(UUID(as_uuid=True), ForeignKey("workflow_node_executions.id", ondelete="SET NULL"), nullable=True)
    checkpoint_type = Column(String(50), nullable=False, index=True)  # OTP, CAPTCHA, DATA_REVIEW, NIC_APPROVAL, FINAL_APPROVAL, EXCEPTION
    status = Column(String(50), nullable=False, default="PENDING", index=True)  # PENDING, RESOLVED, EXPIRED, CANCELLED
    title = Column(String(255), nullable=False)
    prompt_message = Column(Text, nullable=False)
    context_data = Column(JSON, nullable=True)
    resolution_data = Column(JSON, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=_utc_now)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)

    execution = relationship("WorkflowExecution", back_populates="checkpoints")
    application = relationship("Application", back_populates="checkpoints")
    node_execution = relationship("WorkflowNodeExecution", back_populates="checkpoints")
    resolver = relationship("User", foreign_keys=[resolved_by])
