# AINCURU × TAXLA — TECH STACK & INFRASTRUCTURE SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Platform Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Frontend Stack (Next.js)

- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript (strict mode)
- **Styling**: Tailwind CSS, PostCSS
- **Component Library**: shadcn/ui (Radix UI primitives)
- **State & Data Fetching**: React Query (TanStack Query) for API caching. Zustand for global UI state if needed.
- **Form Validation**: React Hook Form + Zod.

## 2. Backend Stack (FastAPI)

- **Language**: Python 3.10+
- **Framework**: FastAPI (ASGI)
- **Data Validation**: Pydantic v2
- **ORM**: SQLAlchemy 2.0 (Async mode)
- **Migrations**: Alembic
- **Task Queue**: Celery (with Redis broker) OR ARQ (Async Redis Queue)
- **Authentication**: PyJWT, Passlib (bcrypt)

## 3. Data & Storage

- **Primary Database**: SQLite (Local Dev) -> PostgreSQL 16 (Production Target)
- **In-Memory Store**: Redis 7+ (Task Queue, Session Caching, Pub/Sub for WebSockets)
- **Object Storage**: Local file system (for MVP synthetic documents). Will migrate to AWS S3 / MinIO.

## 4. AI & Automation Layer

- **OCR Engine**: PaddleOCR (optimized for structured Indian documents) + Tesseract fallback.
- **Local LLM Execution**: Ollama (Local runtime).
- **Primary Model**: Qwen2.5:3b or Llama-3-8B (Quantized) optimized for structured JSON extraction.
- **Automation Runner**: Playwright (Python async API) for browser manipulation and synthetic data injection.

## 5. Development & Deployment Infrastructure

- **Containerization**: Docker & Docker Compose.
- **Environment Management**: `.env` files parsed by `pydantic-settings`.
- **Package Management**: `npm` for frontend, `pip`/`uv` for Python backend.

## 6. Cost & Execution Strategy

- **Zero Cloud AI Costs for Dev**: All LLM processing must run locally via Ollama to ensure data privacy and reduce development API costs.
- **No Cloud Microservices**: The entire stack must be runnable on a single standard developer machine (16GB RAM) using Docker Compose.