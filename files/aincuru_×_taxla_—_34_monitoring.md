# AINCURU × TAXLA — MONITORING & OBSERVABILITY SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Platform Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Structured Logging

`print()` is forbidden in the backend. All logs must use a structured JSON logger (e.g., `structlog` in Python).
- **Required Fields**: `timestamp`, `level`, `request_id`, `application_id`, `user_id`.
- **Severity Levels**: 
  - `INFO`: Normal business events (Workflow started).
  - `WARN`: Retryable transient failures (Udyam portal timeout).
  - `ERROR`: Terminal failures requiring human intervention (LLM hallucination, Schema mismatch).

## 2. Core Metrics (Prometheus/Grafana)

The backend must expose a `/metrics` endpoint tracking:
- **API Metrics**: `http_request_duration_seconds`, `http_requests_total`.
- **Worker Metrics**: `worker_queue_depth` (Redis length), `worker_jobs_completed`, `worker_jobs_failed`.
- **AI Metrics**: `llm_inference_duration_seconds`, `llm_token_usage_total` (if supported by Ollama), `ai_validation_failure_total`.
- **Business Metrics**: `applications_pending_otp`, `applications_completed`.

## 3. Distributed Tracing (Future)

For V1, simple `request_id` propagation is sufficient. In V2, OpenTelemetry will trace the lifespan of a request from the Next.js frontend, through the FastAPI gateway, into the Celery/ARQ worker, and finally to the Ollama container.