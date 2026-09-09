# AINCURU × TAXLA — AUTHENTICATION SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Security Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Authentication Strategy

Taxla V1 uses a standard Email/Password authentication flow secured by stateless JSON Web Tokens (JWT).

## 2. Token Mechanics

- **Format**: JWT (HS256 signature).
- **Payload**: Contains `user_id`, `role`, and `branch_id`. NO sensitive PII.
- **Lifespan**: Short-lived Access Token (15 minutes). Long-lived Refresh Token (7 days).
- **Storage (Frontend)**: Access tokens must be stored in memory or short-lived state (React Query). Refresh tokens must be stored in an `HttpOnly`, `Secure`, `SameSite=Strict` cookie to prevent XSS theft.

## 3. Password Security

- **Hashing**: Passwords are hashed using `bcrypt` (via `passlib`). 
- *Note for V1 Environment*: Due to a known issue with `bcrypt` > 4.0 on Windows, the system strictly pins `bcrypt==3.2.2`.
- **Complexity**: Minimum 8 characters, requiring at least one number and one uppercase letter (enforced by Pydantic schema on registration).

## 4. Endpoint Protection

- All API routes (except `/auth/login` and `/auth/refresh`) must be decorated with FastAPI's `Depends(get_current_user)`.
- If a token is expired or invalid, the API must return a standard `401 Unauthorized`. The frontend Axios interceptor will catch this, attempt a silent refresh using the cookie, and retry the request. If the refresh fails, it redirects to the Login screen.