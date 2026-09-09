# AINCURU × TAXLA — SYSTEM ARCHITECTURE SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Platform Architecture
version: 1.1
target_module: Core Infrastructure
---

## 1. Architectural Style: The Modular Monolith

Taxla V1 is designed as a **Modular Monolith**. It runs as a single deployable unit (FastAPI backend + Next.js frontend) but enforces strict logical boundaries between domains. Microservices are explicitly avoided for V1 to reduce operational overhead, but the codebase is structured so that the `Worker/Playwright` tier and the `AI/LLM` tier can be decoupled into separate services later.

## 2. The 5-Tier Architecture

### Tier 1: UI & Presentation (Next.js / React)
- **Responsibility**: Rendering side-by-side document views, status timelines, and capturing OTPs.
- **Boundary**: Entirely stateless. Communicates exclusively via REST APIs and WebSockets.

### Tier 2: API & Orchestration (FastAPI)
- **Responsibility**: Authenticating requests (JWT), validating input (Pydantic), enforcing RBAC, and interacting with the primary SQL database.
- **Boundary**: Synchronous only. Never blocks on AI generation or Playwright execution. Tasks taking > 500ms are pushed to Redis.

### Tier 3: Core Domain & State persistence (SQLAlchemy / PostgreSQL)
- **Responsibility**: Maintaining the absolute source of truth for `Applications`, `Workflows`, and `AuditLogs`.
- **Boundary**: Implements rigid constraints (Foreign Keys, JSON schemas) to prevent corrupted state.

### Tier 4: Background Execution (Redis Queue / Celery)
- **Responsibility**: Asynchronous execution of heavy tasks (OCR, NIC Classification, Playwright Automation).
- **Boundary**: Workers are stateless and idempotent. If a worker crashes mid-execution, the task can be safely retried or marked as `FAILED`.

### Tier 5: External Interfaces & LLMs (Ollama / Playwright)
- **Responsibility**: Interacting with external reality. Playwright manipulates the real Udyam portal (with synthetic data). Ollama executes local AI prompts.
- **Boundary**: Completely isolated. The core system treats these as unpredictable dependencies, heavily wrapped in retry logic and fallback handlers.

## 3. Synchronous vs Asynchronous Boundaries

**Synchronous (API)**:
- User Authentication.
- Creating an Application.
- Uploading a Document (Binary stored, DB updated, but OCR parsing is sent to Queue).
- Querying Dashboard Stats.
- Submitting an OTP or NIC Approval.

**Asynchronous (Worker Queue)**:
- Running PaddleOCR on uploaded PDFs.
- Querying Ollama for Entity Extraction.
- Generating NIC recommendations.
- Spawning a Playwright headless browser.

## 4. Reliability & Idempotency Rules

1. **State Rehydration**: A Playwright worker must be able to wake up, look at the `workflow_events` table, realize it left off at "Form Page 2", and resume cleanly without restarting from Page 1 (where supported by the portal).
2. **At-Least-Once Delivery**: Redis/Worker tasks must ensure that if a task fails due to a network blip, it is retried automatically.
3. **Pessimistic Locking**: When a worker picks up an application to process, it sets a lock so no other worker attempts to process the same application simultaneously.