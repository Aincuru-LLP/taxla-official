# AINCURU × TAXLA — INTEGRATIONS SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Platform Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. External System Matrix (V1 Demo)

| System | Role | Integration Type | Auth Mechanism |
|---|---|---|---|
| **Udyam Portal (Real)** | Registration Target | Playwright (Browser Automation) | Live Session (with Synthetic Data) |
| **Ollama** | AI Extraction / Reasoning | REST API (Localhost) | None (Network Isolated) |
| **PaddleOCR** | Document Digitization | Python Native bindings | None (In-memory) |

## 2. Integration Principles & The Adapter Pattern

- **Adapter Pattern**: Never call external systems directly from business logic. All external integrations must be wrapped in an `Adapter` class (e.g., `UdyamPortalAdapter`, `LLMAdapter`).
- **Network Isolation**: The LLM and OCR services run on internal Docker networks. They are NOT exposed to the public internet, ensuring PII cannot be accidentally leaked.
- **Resilience**: Every adapter method that makes a network call must implement:
  1. A strict timeout (e.g., 10 seconds for standard APIs, 60 seconds for LLM/Playwright).
  2. Bounded retries (maximum 3 attempts with exponential backoff).
  3. Proper error surfacing (wrapping internal errors in domain-specific `IntegrationError` exceptions).

## 3. Webhook / Callback Future Contract

In production, long-running processes (like Aadhaar verification via NSDL) will require Webhooks.
- **Contract**: Webhooks must support HMAC-SHA256 signature verification.
- **Idempotency**: Webhook handlers must use a unique `event_id` to prevent double-processing.