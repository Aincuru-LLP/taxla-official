# AINCURU × TAXLA — ERROR HANDLING SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Platform Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Standard Error Schema (RFC 7807)

All FastAPI endpoints must return errors in a standardized JSON format. Raw string errors or untyped 500s are forbidden.

```json
{
  "error_code": "RESOURCE_NOT_FOUND",
  "message": "The application 123e4567-e89b-12d3-a456-426614174000 was not found.",
  "details": {
    "entity": "Application",
    "id": "123e4567-..."
  },
  "timestamp": "2024-03-15T12:00:00Z"
}
```

## 2. API Exception Mapping

FastAPI must implement global exception handlers to catch:
- `sqlalchemy.exc.NoResultFound` -> `404 Not Found`
- `sqlalchemy.exc.IntegrityError` -> `409 Conflict`
- `pydantic.ValidationError` -> `422 Unprocessable Entity`
- `auth.InvalidToken` -> `401 Unauthorized`

## 3. Frontend Error Management

- **Global Axios Interceptor**: Catches all 4xx/5xx responses. 
  - `401` triggers a token refresh attempt. If failed, redirects to `/login`.
  - `403` triggers a toast alert: "You do not have permission to perform this action."
- **React Error Boundaries**: Page-level crashes must be caught by Next.js `error.tsx` to prevent blank white screens, showing a stylized "Something went wrong" component with a "Try Again" button.

## 4. Background Worker (Celery/ARQ) Errors

- **Transient Errors** (e.g., Network timeout connecting to Udyam Portal): Retry with exponential backoff (e.g., 5s, 15s, 45s).
- **Terminal Errors** (e.g., Playwright fails to find the main form after 3 retries, LLM outputs garbage 3 times): 
  - Mark task as `FAILED`.
  - Write to `workflow_events`.
  - Alert the UI so a human can intervene. Do NOT silently swallow the error.