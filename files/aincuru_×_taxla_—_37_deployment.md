# AINCURU × TAXLA — DEPLOYMENT SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Platform Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Local Development Stack (Docker Compose)

The entire V1 MVP must run locally via `docker-compose up` without external dependencies.

```yaml
# Topology Map
services:
  frontend: Next.js (Port 3000)
  backend_api: FastAPI (Port 8000)
  backend_worker: Celery/ARQ Worker (No exposed port)
  redis: Message Broker (Port 6379)
```

## 2. Data Persistence (Volumes)

For the demo, state must survive container restarts:
- **SQLite Database**: Mapped to `./backend/data/taxla.db` volume.
- **Redis State**: Mapped to `./backend/data/redis/` volume.
- **Document Storage**: Mapped to `./backend/data/documents/` volume.

## 3. Local LLM Setup (Ollama)

To keep the developer experience fast, Ollama is usually run on the Host machine (macOS/Windows) rather than inside Docker, to easily utilize native GPU acceleration (Metal/CUDA).
- The `backend_api` and `backend_worker` are configured via `.env` to connect to `http://host.docker.internal:11434`.

## 4. Production Target (Future)

- **Compute**: AWS ECS (Fargate) or EKS (Kubernetes).
- **Database**: AWS RDS PostgreSQL 16.
- **Cache/Queue**: AWS ElastiCache (Redis).
- **Storage**: AWS S3 (with KMS Encryption for PII).