# AINCURU × TAXLA — APPLICATION STATE MACHINE SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Core Workflow & Engineering
version: 1.1
target_module: MSME / Udyam Registration Engine (V1)
---

## 1. Application Lifecycle States

Every application instance moves deterministically through defined state nodes. State mutations occur exclusively via validated API calls or background queue events.

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
└────────────┬────────────┘
```

## Failure Handling
An exception records the failed node, reason, retryability and last safe checkpoint. Resumption must continue from a valid persisted state.