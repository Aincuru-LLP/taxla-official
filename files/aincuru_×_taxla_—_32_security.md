# AINCURU × TAXLA — SECURITY SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Security Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Environment Secrets

- **No Hardcoding**: Secrets (JWT Keys, DB URLs, Portal Credentials) MUST NEVER be hardcoded in the repository.
- **Pydantic Settings**: Backend configuration is strictly managed via `pydantic-settings` reading from `.env`. If a required secret is missing at startup, the server MUST crash immediately.

## 2. Identity Document Isolation (PII)

Even though V1 uses synthetic data, it is architected as if it handles real PII.
- **No Cloud AI APIs**: Documents (Aadhaar/PAN) must NEVER be sent to OpenAI, Anthropic, or external APIs. All extraction MUST happen locally via PaddleOCR and Ollama.
- **Storage**: Uploaded PDFs/JPGs are stored on a local disk volume (for MVP). They must not be publicly accessible via a static URL. They are served via an authenticated `/api/v1/documents/{id}/download` endpoint.

## 3. Data Scrubbing & Logging

- Passwords, OTPs, and JWTs must NEVER be printed to standard output or log files.
- When an API request fails, the `422 Unprocessable Entity` response must not leak stack traces or internal DB schema details.

## 4. Frontend Security

- **XSS Prevention**: React handles HTML escaping by default. Avoid `dangerouslySetInnerHTML`.
- **CORS**: FastAPI CORS middleware must explicitly define allowed origins (e.g., `http://localhost:3000`). Wildcard `*` is forbidden.