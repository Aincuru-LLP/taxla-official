# AINCURU × TAXLA — OTP & HUMAN APPROVAL CHECKPOINT SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Workflow & UI Engineering
version: 1.1
target_module: MSME / Udyam Registration Engine (V1)
---

## 1. Human-in-the-Loop Protocol Architecture

Certain compliance operations (such as official OTP verification or final submission sign-off) CANNOT be automated without explicit human authorization. The system implements a resilient **Async Pause & Resume Handshake Protocol**.

```text
[Playwright Worker Process]                      [Next.js Operator Dashboard UI]
             │                                                  │
             │ Triggers OTP Step on Portal                      │
             │ Captures Screenshot & Saves Checkpoint           │
             │ Emits Redis Event `OTP_REQUIRED`                 │
             ├─────────────────────────────────────────────────►│
             │                                                  │ Displays Live Screenshot,
             │ Pauses Async Worker (Listens on Redis Pub/Sub)  │ Alert Badge & Countdown Timer
             │                                                  │
             │                                                  │ Operator enters OTP (e.g. "123456")
             │                                                  │ POST /api/v1/applications/{id}/otp
             │                                                  │
             │ Receives Redis Signal `otp_submitted`            │
             │◄─────────────────────────────────────────────────┤
             │ Injects OTP into Portal DOM                      │
             │ Resumes Browser Execution Flow                   │
```

---

## 2. API Endpoint & Validation Payload

### REST API: Submit OTP Code
- **Method**: `POST`
- **Path**: `/api/v1/applications/{id}/otp`
- **Request Body**:
  ```json
  {
    "otp_code": "123456",
    "checkpoint_id": "STEP_1_OTP_WAIT"
  }
  ```
- **Response**: `200 OK`
  ```json
  {
    "status": "OTP_ACCEPTED",
    "message": "OTP dispatched to Playwright browser context.",
    "application_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "timestamp": "2026-08-31T12:00:00Z"
  }
  ```

---

## 3. Human Approval Checkpoints & Timeout Safety

| Checkpoint Name | Trigger State | Human Action Required | Timeout Duration | Timeout Fallback Action |
| :--- | :--- | :--- | :--- | :--- |
| **OCR / Extraction Verification** | `EXTRACTED` | Confirm low-confidence fields on side-by-side UI screen. | 24 Hours | Application remains paused in `EXTRACTED`. |
| **NIC Classification Approval** | `NIC_REVIEW` | Click "Confirm NIC Selection" (or choose alternate 5-digit code). | 24 Hours | Application remains paused in `NIC_REVIEW`. |
| **Portal OTP Verification** | `OTP_REQUIRED` | Input 6-digit OTP received on synthetic applicant mobile. | 180 Seconds (3 Mins) | State moves to `EXCEPTION` (`OTP_TIMEOUT`); worker releases browser context. |
| **Final Submission Authorization**| `HUMAN_REVIEW` | Reviewer / Auditor clicks "Authorize Portal Submission". | 12 Hours | Application remains in `HUMAN_REVIEW`. |

---

## 4. Immutable Audit Log Requirements

Every human approval interaction records:
1. `actor_id`: UUID of operator/reviewer logged in.
2. `action`: `APPROVE_NIC`, `SUBMIT_OTP`, `AUTHORIZE_SUBMISSION`, or `REJECT_APPLICATION`.
3. `ip_address` & `user_agent`: Network security parameters.
4. `metadata_json`: Diff of fields edited, original AI values vs selected values, and execution duration.

## Rules
- OTP is never generated or guessed by AI.
- OTP values must not be logged.
- Human approval is explicit and auditable.
- Rejection must capture a reason.
- Expired/invalid OTP returns the application to the appropriate retry state.