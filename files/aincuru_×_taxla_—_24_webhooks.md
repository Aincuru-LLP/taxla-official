# AINCURU × TAXLA — WEBHOOKS & CALLBACKS SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Platform Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Internal Continuation Webhooks (V1)

While Taxla V1 does not ingest external partner webhooks, it heavily relies on **Internal Continuation Webhooks**. 
When a Playwright worker pauses for OTP, it cannot block the thread. It suspends and waits. When the human enters the OTP in the UI, the frontend calls a FastAPI route, which in turn acts as an internal webhook, firing an event to Redis to resume the exact worker session.

## 2. Production Webhook Contract (V2+)

When integrating with third-party verification APIs (e.g., DigiLocker, NSDL):
- **Endpoint Design**: Webhook receivers must be distinct from standard REST endpoints (e.g., `/api/v1/webhooks/nsdl`).
- **Security Validation**: 
  1. Verify the `X-Hub-Signature` (HMAC SHA-256) using the partner's provisioned secret.
  2. Reject payloads missing signatures or timestamps older than 5 minutes.
- **Async Processing**: A webhook endpoint MUST respond `202 Accepted` immediately after validating the signature and persisting the raw payload. Business logic MUST NOT be processed synchronously within the webhook HTTP request.
- **Idempotency**: Use the partner's unique `transaction_id` as the Redis lock key to discard duplicate retries.