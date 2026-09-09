# AINCURU × TAXLA — TESTING SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: QA & Platform Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. The Testing Pyramid

- **Unit Tests (Pytest)**: Fast, isolated tests for Pydantic validators, business logic pure functions, and Regex utilities.
- **Integration Tests (Pytest + TestContainers)**: Tests against a real local SQLite/PostgreSQL instance. Asserts that FastAPI routes correctly read/write to the DB and enforce RBAC.
- **AI Contract Tests**: Uses the `tests/ai_eval_data/` dataset to verify prompt changes don't degrade parsing quality.
- **E2E UI Tests (Playwright)**: Full browser tests that log into the Next.js app, upload a synthetic document, and click through the workflow.

## 2. The Critical Path Test (Must Pass in CI)

A PR cannot be merged unless this End-to-End flow passes entirely unattended:
1. `POST /api/v1/applications` (Create)
2. `POST /api/v1/documents` (Upload synthetic Aadhaar)
3. Wait for `status == PAUSED_FOR_REVIEW`
4. `POST /api/v1/applications/{id}/approve_data` (Operator Action)
5. Wait for `status == NIC_REVIEW_APPROVED`
6. `POST /api/v1/applications/{id}/start_automation` (Trigger Worker)
7. Wait for `status == WAITING_FOR_OTP`
8. `POST /api/v1/applications/{id}/submit_otp` (Submit OTP `123456`)
9. Wait for `status == COMPLETED`

## 3. Mocking External Boundaries in CI

- The **Real Udyam Portal** must not be spammed in automated CI tests to avoid IP bans. CI tests should stub Playwright responses or run against a local mock container specifically for unit/integration tests, while the actual demo and staging environment will run against the real portal.
- The **Ollama Service** can be mocked in standard Integration tests using a MockAdapter that returns hardcoded valid/invalid JSON strings to test pipeline resilience.