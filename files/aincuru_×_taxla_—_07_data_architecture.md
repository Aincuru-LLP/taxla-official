# AINCURU × TAXLA — DATA ARCHITECTURE SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Data Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Data Lineage & Lifecycle

The system enforces strict chronological lineage. Data mutation is unidirectional.

```text
1. RAW DOCUMENT (Binary PDF/JPG) 
   → Stored in `documents` (disk path).
2. RAW OCR TEXT (Unstructured String) 
   → Not permanently persisted, passed in memory to LLM.
3. EXTRACTED ENTITIES (JSON) 
   → Stored in `extracted_data` with `confidence_score` and `source_document_id`.
4. VALIDATED ENTITIES 
   → Operator approves/mutates `extracted_data`. `validation_status` becomes `VERIFIED`.
5. DOMAIN STATE 
   → Verified fields are hydrated into the canonical `Application` entity.
6. EXTERNAL MUTATION 
   → Canonical data is injected into the real Udyam portal via Playwright.
7. FULFILLMENT 
   → Output (Certificate PDF) is saved, linking back to `Application`.
```

## 2. Core Data Principles

- **Separation of Raw vs Canonical**: Raw OCR output is never saved directly to the business entity. It must pass through the `extracted_data` validation table first.
- **Traceability**: Every row in `extracted_data` MUST map to a `source_document_id`.
- **Immutable Auditing**: Every human validation, NIC approval, and OTP injection MUST generate an immutable `AuditLog` row.
- **Soft Deletion**: Records are soft-deleted via status flags (`status="DELETED"`) or cascaded ONLY if explicitly authorized (e.g. wiping synthetic data).

## 3. Storage & Security (Demo Environment)

- **Transient Document Storage**: Documents uploaded to the local filesystem must be stored in isolated, application-specific folders (e.g., `./storage/documents/{application_id}/`).
- **PII Scrubbing**: While the demo uses synthetic data, the architecture treats all data as real PII. Passwords are hashed with `bcrypt`. In production, Aadhaar hashes will be generated and plain text Aadhaars dropped immediately after portal injection.
- **No Cloud Leaks**: No documents or extracted data will be sent to external APIs (OpenAI, Anthropic). All processing remains strictly local via Ollama and PaddleOCR.