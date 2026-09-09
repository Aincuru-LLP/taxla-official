# AINCURU × TAXLA — EXECUTION ENGINE SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Platform Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Engine Objective

To safely and reliably execute long-running asynchronous tasks (OCR, Playwright, LLM inference) outside of the FastAPI request-response lifecycle.

## 2. Worker & Queue Architecture

The system uses **Redis** as a broker and a standard async task queue (e.g., **ARQ** or **Celery**). 

### Queue Topologies
- `default_queue`: Fast, lightweight tasks (sending emails, updating status). Concurrency: 10+.
- `ai_queue`: Heavy CPU bound tasks (Ollama, OCR). Concurrency: 1 or 2 (to prevent OOM on local metal).
- `browser_queue`: Playwright headless runners. Concurrency: 3-5 (memory intensive).

## 3. Execution Lifecycle & Locks

```text
1. API Enqueues Task -> `enqueue_job('run_ocr', app_id=123)`
2. Worker Claims Job
3. Worker Acquires Distributed Lock -> `SETNX lock:app:123`
4. Worker Executes -> (Logs start to `workflow_events`)
5. Worker Completes -> (Updates DB, Logs completion)
6. Worker Releases Lock
```

## 4. Idempotency & Concurrency Rules

- **Pessimistic Locking**: An application can only be processed by one worker at a time. The distributed Redis lock prevents race conditions (e.g., clicking "Approve" twice quickly).
- **Idempotency**: If `run_ocr` crashes midway, the retry mechanism must cleanly overwrite previous extraction attempts or resume without duplicating records in `extracted_data`.
- **No Blocking on Humans**: A worker executing Playwright MUST NOT block its thread waiting for an OTP. It must yield/suspend, freeing up the concurrency slot, and be re-awoken by the API when the OTP is supplied.