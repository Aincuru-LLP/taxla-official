# AINCURU × TAXLA — PRODUCT REQUIREMENTS DOCUMENT (PRD)

---
status: APPROVED SPECIFICATION
owner: Product & Engineering
version: 1.1
target_module: MSME / Udyam Registration Engine (V1)
---

## 1. Product Summary & Goal

The **Taxla MSME / Udyam Registration Engine V1** automates end-to-end Udyam registration for micro, small, and medium enterprises in India. It accepts synthetic identity and financial documents, extracts key entity attributes using local OCR/AI models, performs validation, assists operators with 5-digit NIC code selection, executes browser-based submission on the real Udyam portal via Playwright (using synthetic data for safety), manages OTP pause-and-resume workflows, and delivers a downloadable Udyam Certificate with audit tracking.

---

## 2. Core Operational Persona & Workflows

1. **Operator (Primary Persona)**:
   - Ingests applicant data and synthetic identity documents.
   - Verifies OCR extraction and validation alerts on the side-by-side verification screen.
   - Confirms or adjusts AI-recommended NIC 5-digit codes.
   - Monitors automated portal execution and enters OTP when prompted.
2. **Reviewer / Auditor**:
   - Oversees flagged/exception cases.
   - Performs pre-submission authorization checks.
3. **Branch Admin / Super Admin**:
   - Assigns applications and monitors branch SLAs and audit trails.

---

## 3. System Inputs, Processing & Outputs

### Inputs
- **Document Files**: PDF, PNG, JPG uploads of Aadhaar Card, PAN Card, and Bank Statement / Cancelled Cheque.
- **Form Parameters**: Applicant name, mobile number, email address, enterprise type (Micro/Small/Medium), social category, unit location details, and business activity text.
- **Human Controls**: Selected NIC codes, OTP code, and submission approval decision.

### Processing Pipeline
1. **Document Ingestion & Parsing**: File type validation, resolution check, PaddleOCR/Tesseract text extraction.
2. **Field Extraction & Normalization**: Extraction of PAN number, Aadhaar number, IFSC code, account number, applicant name, and address.
3. **Deterministic Validation**: Regex checks (PAN format `[A-Z]{5}[0-9]{4}[A-Z]{1}`, Aadhaar 12 digits, IFSC format), mandatory field completeness, name fuzzy matching across PAN and Aadhaar.
4. **NIC Classification**: LLM-driven activity semantic analysis against official 2008 5-digit NIC code index.
5. **Browser Automation**: Playwright multi-step navigation, form filling, screenshot capturing, and element state verification.

### Outputs
- Normalized JSON application payload.
- Field-level OCR extraction confidence scores (0.0 to 1.0).
- Top 3 ranked 5-digit NIC recommendations with rationale.
- Live browser screenshot stream during portal automation.
- Generated Udyam Registration Certificate (PDF format).
- Complete immutable audit trajectory log.

---

## 4. Edge Cases & Resilience Rules

| Failure Scenario | Detection Mechanism | System Action & Recovery |
| :--- | :--- | :--- |
| **Unreadable Document / Low OCR Score** | Extraction confidence < 0.70 | Flag field with warning badge (`LOW_CONFIDENCE`); highlight bounding box on image in UI for manual operator entry. |
| **Name Mismatch Across Docs** | Levenshtein distance > 0.15 between PAN and Aadhaar | Transition to `VALIDATION` error state; prompt operator to select official legal name. |
| **Invalid Regex Format** | Pydantic regex validator failure | Block transition to `NIC_REVIEW`; highlight invalid input field in red with error message. |
| **OTP Input Timeout** | Operator fails to submit OTP within 180 seconds | Playwright context pauses; state changes to `EXCEPTION` (`OTP_TIMEOUT`); provide "Resend OTP" button. |
| **Portal DOM Selector Failure** | Playwright element timeout | Capture error screenshot; trigger exception alert; log DOM snapshot for developer debugging. |

---

## 5. Acceptance Criteria & Definition of Done

- [x] Application can be created via REST API or Next.js Web UI.
- [x] Uploaded documents trigger asynchronous OCR worker jobs without UI thread blocking.
- [x] Data extraction populates structured fields with confidence scores.
- [x] NIC engine presents 5-digit codes with descriptions; human click commits choice.
- [x] Playwright worker launches real portal browser, populates form fields, and emits `OTP_REQUIRED`.
- [x] UI displays live screenshot of the portal during OTP wait state.
- [x] Entering valid OTP triggers portal resumption and final submission.
- [x] Udyam certificate is generated (or simulated completion if aborting before final live bind for safety), downloadable, and linked to application record.
- [x] Full audit log captures actor, action, timestamp, and state diff for every transition.