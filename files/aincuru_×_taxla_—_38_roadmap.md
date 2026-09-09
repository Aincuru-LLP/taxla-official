# AINCURU × TAXLA — PRODUCT ROADMAP

---
status: APPROVED SPECIFICATION
owner: Product Leadership
version: 1.1
target_module: Product Planning
---

## Phase 1: The Core Engine (MSME MVP) - CURRENT
- **Goal**: End-to-end automation of a single Udyam registration using synthetic data against the real portal.
- **Deliverables**: 5-Tier Architecture, AI Extraction (PaddleOCR+Ollama), Human-in-the-loop review screens, OTP suspension worker logic.
- **Exit Criteria**: A flawless, uninterrupted demonstration of the happy path + one AI failure recovery path on the real Udyam site.

## Phase 2: Production Hardening
- **Goal**: Move from Synthetic to Real Customer Data.
- **Deliverables**: AWS S3 KMS integration, RDS PostgreSQL migration, comprehensive E2E Pytest suites.
- **Exit Criteria**: First successful real business registration in production.

## Phase 3: GST Registration Automation
- **Goal**: Horizontal expansion into complex tax registrations.
- **Deliverables**: New DAG workflow nodes, complex multi-document AI extraction (address proofs, lease agreements).

## Phase 4: Financial Ledger Ingestion (Tally)
- **Goal**: Automate ongoing compliance (Bank statements/Invoices -> Tally).
- **Deliverables**: Heavy PDF table extraction models, bulk processing concurrency tuning.

## Phase 5: Reconciliation & Exceptions
- **Goal**: GST vs ITC reconciliation.
- **Deliverables**: AI discrepancy detection, client-facing communication webhooks.

## Phase 6 & 7: Intelligence (Advisory & Notices)
- **Goal**: Tax notice response drafting and financial statement generation using RAG on compliance law.

*(Note: Features beyond Phase 1 must NOT pollute the Phase 1 codebase until Phase 1 is officially complete.)*