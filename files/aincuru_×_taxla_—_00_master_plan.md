# AINCURU × TAXLA — MASTER PLAN

---
status: APPROVED FOUNDATION
owner: AINCURU Engineering & Product Team
version: 1.1
scope: Taxla Enterprise Automation Platform — MSME / Udyam Registration V1 & Reusable Core Foundation
---

## 1. Executive Summary & Core Principle

AINCURU is engineering an enterprise-grade compliance and workflow automation platform for **Taxla**. The platform transitions document-heavy, manual compliance services into structured, observable, and automated digital pipelines while guaranteeing human oversight for sensitive operations.

The foundational design mandate is:

> **"AI interprets. Software validates. Automation executes. Humans approve. The system records everything."**

### Taxla 5-Tier Blueprint Integration

1. **Tier 1 — Intake & Parsing Layer**: Document ingest (Aadhaar, PAN, Bank Proof), OCR/Text extraction, image preprocessing, document classification, and confidence scoring.
2. **Tier 2 — Domain Calculation & Mapping Layer**: Business rule validation, data format standardization, NIC 2/4/5-digit activity classification, and cross-field consistency checks.
3. **Tier 3 — Human-in-the-Loop Checkpoint**: Verification interface for low-confidence extractions, NIC code selection/override, OTP entry, and final submission authorization.
4. **Tier 4 — Browser & Service Automation**: Playwright-driven headless/headed browser execution against the real official Udyam portal, resilient step execution, DOM interaction, screenshot capture, and state resumption.
5. **Tier 5 — Persistence & Audit Engine**: Immutable event logging, state tracking, workflow history, document storage, and analytical monitoring.

---

## 2. Product Hierarchy & Scalability Blueprint

```text
AINCURU Core Platform Engine
        │
        ├── Taxla Compliance Automation System
        │     │
        │     ├── Reusable Automation & Integration Core
        │     │     ├── Document Intake & OCR Pipeline
        │     │     ├── Generic State Machine & Workflow Execution Engine
        │     │     ├── Playwright Web Automation Framework
        │     │     ├── Human Checkpoint & Notification Broker
        │     │     └── Immutable Audit & Telemetry Suite
        │     │
        │     ├── V1 Core Module: MSME / Udyam Registration Engine
        │     │     ├── Identity & Bank Document Processor
        │     │     ├── Smart NIC Code Recommendation Engine (2008 Standard)
        │     │     ├── Official Udyam Portal Playwright Controller
        │     │     └── OTP Handshake & Verification Manager
        │     │
        │     └── Scalable Future Modules (Pluggable Micro-verticals)
        │           ├── Module 02: GST Registration Engine
        │           ├── Module 03: Bank & Invoice → Tally Automation Engine
        │           ├── Module 04: GST / ITC Reconciliation Engine
        │           ├── Module 05: Financial Statement Extraction & Ratio Engine
        │           └── Module 06: AI Tax Notice Assistant & Defense Generator
```

---

## 3. End-to-End V1 MSME / Udyam Flow

```text
[Operator/Client]
       │ Create Application & Upload Synthetic Docs (PAN, Aadhaar, Bank Statement)
       ▼
[Tier 1: Document Processing Worker]
       │ OCR Extraction (PaddleOCR / Tesseract) + Pydantic Schema Parsing
       ▼
[Tier 2: Validation Engine & AI NIC Engine]
       │ Validate Regex (PAN/Aadhaar/IFSC), Check Completeness
       │ Query Ollama LLM + NIC Embedding Index → Rank top 5-digit NIC Codes
       ▼
[Tier 3: Human Review Checkpoint (Operator UI)]
       │ Side-by-Side Review of Extracted Data vs Document Image
       │ Confirm/Override NIC Classification → Click "Approve for Portal Execution"
       ▼
[Tier 4: Playwright Browser Worker]
       │ Launch Isolated Browser Context → Navigate Real Udyam Portal
       │ Fill Step 1 (Aadhaar & Name) → Click "Validate & Generate OTP"
       │ Portal Triggers OTP → Browser Worker Pauses & Emits `OTP_REQUIRED` Event
       ▼
[Tier 3: Human OTP Checkpoint (Operator UI)]
       │ UI Displays Live Browser Screenshot & Countdown Timer
       │ Operator Inputs OTP → POST `/api/v1/applications/{id}/otp`
       ▼
[Tier 4: Playwright Browser Worker Resumed]
       │ Inject OTP into Browser Session → Complete Step 2 Form (PAN, Address, NIC)
       │ Perform Final Verification → Submit Application → Capture Certificate PDF
       ▼
[Tier 5: Persistence & Notification Engine]
       │ Save Certificate PDF to Storage → Update Application Status to `COMPLETED`
       │ Emit Final Audit Event → Render Timeline in Operator Dashboard
```

---

## 4. Non-Negotiable Engineering Principles

1. **Context Before Technology**: Architecture prioritizes domain correctness, user workflows, and state reliability over arbitrary tech trends.
2. **Deterministic Rules Over Probabilistic AI**: AI is strictly used for extraction, classification, and drafting. All validation, state transitions, security checks, and database mutations are governed by explicit code rules.
3. **Fail-Safe Human Control**: Sensitive actions (portal submission, financial edits, identity verification) strictly require human approval.
4. **Observable & Resumable State**: Every application state transition is saved in PostgreSQL with Redis queue checkpoints. If a browser worker crashes or times out, the process can resume from the exact last successful checkpoint.
5. **Strict Modular Monolith**: Code is cleanly partitioned into domain modules (`document`, `nic`, `workflow`, `automation`, `audit`). Monolith structure is maintained for high cohesion and single-command local deployment during V1.
6. **Synthetic Data Sandbox**: All V1 development and demonstration scenarios exclusively use synthetic identity, financial, and portal environment data.

---

## 5. User Roles & Permission Hierarchy

| Role | Access Scope | Operational Capabilities |
| :--- | :--- | :--- |
| **Super Admin** | Platform-Wide | Organization setup, branch creation, system configuration, global user management, complete audit log inspection, AI model parameters. |
| **Branch Admin** | Branch-Scoped | Assign applications to operators, monitor branch performance metrics, oversee reviewer queues, manage branch user accounts. |
| **Operator** | Assigned Apps | Create applications, upload client documents, verify OCR extractions, handle OTP input checkpoints, resolve missing field errors. |
| **Reviewer / Auditor** | Assigned / Escalated | Review high-value or low-confidence applications, perform final submission authorization, audit state history, reject invalid applications. |

---

## 6. Comprehensive Application State Machine

```text
       ┌───────────┐
       │    NEW    │
       └─────┬─────┘
             │ Document Uploaded
             ▼
┌─────────────────────────┐
│   DOCUMENTS_UPLOADED    │
└────────────┬────────────┘
             │ Dispatch OCR Job
             ▼
┌─────────────────────────┐
│       PROCESSING        │
└────────────┬────────────┘
             │ OCR & Field Parsing Complete
             ▼
┌─────────────────────────┐
│        EXTRACTED        │
└────────────┬────────────┘
             │ Deterministic Validation Engine
             ▼
┌─────────────────────────┐      Validation Failed
│       VALIDATION        ├─────────────────────────────┐
└────────────┬────────────┘                             │
             │ Validation Passed                        │
             ▼                                          ▼
┌─────────────────────────┐                 ┌───────────────────────┐
│       NIC_REVIEW        │                 │       EXCEPTION       │
└────────────┬────────────┘                 │  (Requires Operator) │
             │ Human Approved NIC Selection         └───────────┬───────────┘
             ▼                                          │ Fixed / Resolved
┌─────────────────────────┐                             │
│    READY_FOR_PORTAL     │◄────────────────────────────┘
└────────────┬────────────┘
             │ Dispatch Browser Worker
             ▼
┌─────────────────────────┐
│     PORTAL_RUNNING      │
└────────────┬────────────┘
             │ Reaches OTP Step
             ▼
┌─────────────────────────┐
│      OTP_REQUIRED       │
└────────────┬────────────┘
             │ Operator Inputs OTP
             ▼
┌─────────────────────────┐
│       OTP_VERIFIED      │
└────────────┬────────────┘
             │ Form Completion Done
             ▼
┌─────────────────────────┐
│      HUMAN_REVIEW       │
└────────────┬────────────┘
             │ Final Submission Approval
             ▼
┌─────────────────────────┐
│        APPROVED         │
└────────────┬────────────┘
             │ Submit to Portal
             ▼
┌─────────────────────────┐
│       SUBMITTING        │
└────────────┬────────────┘
             │ Portal Confirmation Received
             ▼
┌─────────────────────────┐
│        SUBMITTED        │
└────────────┬────────────┘
             │ Certificate Extracted
             ▼
┌─────────────────────────┐
│    CERTIFICATE_READY    │
└────────────┬────────────┘
             │ Archive & Notify Client
             ▼
┌─────────────────────────┐
│        COMPLETED        │
└─────────────────────────┘
```

---

## 7. Recommended Technology Baseline

- **Frontend**: Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui, Lucide Icons, React Query, Zustand.
- **Backend API**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (AsyncIO), Alembic.
- **Data Persistence**: PostgreSQL 16 (Primary DB), Redis 7 (Caching, Queue Broker, Pub/Sub).
- **Task Queue & Workers**: Redis Task Queue (RQ) or Celery with async background processing.
- **Document AI / OCR**: PaddleOCR (Primary for formatted documents), Tesseract (Fallback), PyMuPDF / pdf2image.
- **Local AI Service**: Ollama hosting open-weight models (`llama3`, `mistral`, or `qwen2.5`) for business parsing and NIC classification.
- **Browser Automation**: Playwright Python (Chromium context, headless/headed toggles, screenshot streaming).
- **Containerization & Dev Ops**: Docker Compose for single-command orchestration, Nginx reverse proxy.

---

## 8. Definition of Demo Success

The V1 Demonstration is successful when a Taxla operator can seamlessly process a synthetic business client application from initial document drop to final Udyam certificate acquisition within the unified workspace:

1. **Document Intake**: Drag-and-drop PAN, Aadhaar, and Bank Proof.
2. **Extraction Verification**: Instant visual side-by-side verification showing extracted values and confidence badges.
3. **AI Assistance**: Automatic ranking and display of 5-digit NIC codes based on business description with 1-click human selection.
4. **Live Web Automation**: Real-time Playwright execution against the interactive Real Udyam Portal, streaming step progress and browser screenshots.
5. **Human OTP Handshake**: Immediate UI pause at the OTP step, prompt for operator input, and automatic browser resumption.
6. **Certificate & Audit Log**: Instant generation and storage of the Udyam Registration Certificate accompanied by a timestamped, immutable audit log.