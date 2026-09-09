# AINCURU × TAXLA — MVP SCOPE & DEMO BOUNDARIES

---
status: APPROVED SPECIFICATION
owner: Product & Engineering
version: 1.1
target_module: MSME / Udyam Registration Engine (V1)
---

## 1. Objective

To deliver a completely functional, end-to-end automation of the **MSME / Udyam Registration** workflow that operates locally on synthetic data, proving the viability of the Taxla 5-Tier Architecture without requiring real government API keys or exposing real customer PII.

## 2. In-Scope: MUST BUILD (The Golden Path)

### 2.1 Core Infrastructure
- Local SQLite / PostgreSQL database with full schema migrations (Alembic).
- FastAPI backend serving structured REST endpoints.
- Next.js (React) frontend with a side-by-side verification interface.
- Redis-backed background worker queue (e.g., Celery/ARQ) for asynchronous tasks.

### 2.2 AI & Document Pipeline
- **Document Ingestion**: Upload Aadhaar, PAN, and Bank Proof (PDF/JPG/PNG).
- **OCR Engine**: Extract raw text using PaddleOCR / Tesseract.
- **Entity Extraction**: Use Local LLM (Ollama / Qwen2.5) with structured output (JSON) to extract Name, PAN, Aadhaar Number, and Bank IFSC.
- **NIC Classification**: Vector-based semantic search + LLM reranking to map user-provided business descriptions to official NIC 2008 codes.

### 2.3 Workflow Execution & Playwright
- **State Machine**: Deterministic state progression (`NEW` -> `EXTRACTED` -> `NIC_REVIEW` -> `PORTAL_RUNNING` -> `OTP_REQUIRED` -> `APPROVED`).
- **Real Government Portal (Synthetic Data)**: The automation targets the actual live Udyam portal. However, to prevent polluting government databases, the script will use synthetic test data and gracefully abort/simulate success right before the final binding submission step. No local mock server is needed.
- **Playwright Worker**: A headless browser worker that navigates the real portal, injects extracted data, solves required Captchas (or prompts for them), and pauses when OTP is required.

### 2.4 Human-in-the-Loop
- WebSockets or polling to notify the UI when the Playwright worker is paused.
- Operator enters OTP in the UI, and Playwright injects it and resumes.

## 3. Out-of-Scope: DO NOT BUILD FOR DEMO

- Production deployment pipelines (Kubernetes/Helm).
- Billing, Stripe integrations, or multi-tenant SaaS features.
- Actual interactions with the real `udyamregistration.gov.in` portal.
- GPU clustering or multi-node LLM serving (Ollama runs locally on CPU/Metal).
- Complex visual workflow builders (Node-RED style interfaces).

## 4. Definition of Done (DoD)

1. **Golden Path Success**: A user can upload synthetic documents; the system extracts the data; the user approves the NIC code; the system drives the real Udyam portal via Playwright; the system pauses; the user provides an OTP/Captcha; the system finishes the workflow.
2. **Concurrency**: The system can handle Application B uploading documents while Application A is paused waiting for an OTP.
3. **Traceability**: Every step is logged in `audit_logs` and `workflow_events`.