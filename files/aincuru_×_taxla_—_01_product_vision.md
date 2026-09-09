# AINCURU × TAXLA — PRODUCT VISION

---
status: APPROVED SPECIFICATION
owner: Product & Engineering
version: 1.1
target_module: MSME / Udyam Registration Engine (V1)
---

## 1. Vision & Core Philosophy

**TAXLA** is an enterprise-grade automation platform designed to execute complex, multi-step compliance operations with deterministic reliability. The core philosophy is **"Deterministic Automation around Probabilistic AI"**. AI is used to extract, classify, and recommend, but human operators and hard-coded business logic always maintain final authority before state mutation or external execution.

## 2. The Problem Space

Tax, compliance, and corporate secretarial work suffer from:
1. **Unstructured Ingestion**: Clients provide photos, skewed PDFs, and raw text across channels.
2. **High Cognitive Load Data Entry**: Operators must manually locate PAN numbers, Aadhaar hashes, bank details, and match business descriptions to archaic government taxonomies (e.g., NIC 2008 codes).
3. **Brittle Portal Interaction**: Government portals have unpredictable latency, frequent captchas, and synchronous OTP requirements.
4. **Scattered State**: Keeping track of which application is waiting for documents, waiting for NIC review, or waiting for an OTP is a manual, spreadsheet-driven process.

## 3. Product Promise & Guarantees

Taxla guarantees:
- **Zero Silent Failures**: If OCR confidence is low, if an AI extraction fails a regex check, or if a Playwright script cannot find a DOM element, the system immediately pauses and escalates to a human operator.
- **Full Traceability**: Every automation step, API call, AI prompt, and human decision is immutably logged in the `audit_logs` and `workflow_events` tables.
- **Asynchronous Execution with Synchronous Pauses**: Workflows run in background task queues (Redis/Celery) but cleanly pause execution and serialize state to wait for synchronous human input (like an OTP).

## 4. V1 Focus: MSME / Udyam Registration

The V1 system proves the architecture by automating the **MSME / Udyam Registration Workflow**:
1. **Intake**: Accept Aadhaar, PAN, and Bank Proof.
2. **Extract & Classify**: OCR extraction, Regex validation, and AI-driven NIC Code recommendation (2, 4, 5-digit mapping).
3. **Human Review**: Side-by-side UI comparing raw documents against extracted data and AI NIC recommendations.
4. **Execution**: Playwright-driven browser automation against the real Udyam portal (using synthetic data).
5. **Checkpoint**: Pause for Aadhaar OTP, capture via UI, inject into headless browser.
6. **Fulfillment**: Download Registration Certificate and close the loop.

## 5. Scalability & Future Horizons

The underlying 5-Tier architecture (Data, Workflow, AI, Execution, UI) is built to be horizontally scalable and functionally generic. By swapping the Document Pipeline and Playwright target, the same foundation will support:
- GST Registration & Return Filing
- Bank Statement to Tally Reconciliation
- MCA Company Incorporation
- Income Tax Notice Response Generation