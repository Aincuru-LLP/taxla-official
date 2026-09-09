# API SPEC

## Application
```text
POST   /applications
GET    /applications
GET    /applications/{id}
PATCH  /applications/{id}
```

## Documents
## AINCURU × TAXLA — REST API SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Backend Engineering
version: 1.1
target_framework: FastAPI 0.110+
---

## 1. API Architecture & Standards

- **Base URL**: `http://localhost:8000/api/v1`
- **Authentication**: OAuth2 Password Bearer with JWT tokens (`Authorization: Bearer <token>`).
- **Data Serialization**: JSON payloads strictly validated via Pydantic v2 schemas.
- **Error Response Protocol**: RFC 7807 Problem Details compliant error objects.

---

## 2. Exhaustive API Endpoints

### Auth Domain (`/api/v1/auth`)

#### `POST /auth/login`
- **Description**: Authenticate user and issue JWT token.
- **Request (OAuth2 Form / JSON)**:
  ```json
  {
    "username": "operator@taxla.com",
    "password": "SecurePassword123!"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
    "token_type": "bearer",
    "user": {
      "id": "c1f7b8a0-2f3a-4a2e-8d1e-9f3a4b5c6d7e",
      "name": "Taxla Operator",
      "email": "operator@taxla.com",
      "role": "OPERATOR",
      "branch_id": "b1f7b8a0-2f3a-4a2e-8d1e-9f3a4b5c6d7e"
    }
  }
  ```

---

### Application Domain (`/api/v1/applications`)

#### `POST /applications`
- **Description**: Create a new MSME registration application instance.
- **Request Body**:
  ```json
  {
    "branch_id": "b1f7b8a0-2f3a-4a2e-8d1e-9f3a4b5c6d7e",
    "business_name": "Acme Tech Solutions",
    "applicant_name": "Rajesh Kumar",
    "mobile_number": "+919876543210",
    "email": "rajesh@acmetech.com",
    "pan_number": "ABCDE1234F",
    "aadhaar_number": "123456789012"
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "application_number": "UDYAM-2026-08-0001",
    "status": "NEW",
    "created_at": "2026-08-31T11:50:00Z"
  }
  ```

#### `GET /applications`
- **Description**: List applications with pagination and filters.
- **Query Parameters**: `status`, `branch_id`, `assigned_to`, `page` (default 1), `limit` (default 20).

#### `GET /applications/{id}`
- **Description**: Retrieve detailed application record including documents, OCR extractions, NIC suggestions, and state timeline.

---

### Document Domain (`/api/v1/applications/{id}/documents`)

#### `POST /applications/{id}/documents`
- **Description**: Upload synthetic identity document file (Multipart Form Data).
- **Form Data**: `file` (Binary), `document_type` (`PAN_CARD` | `AADHAAR_CARD` | `BANK_PROOF`).
- **Response `202 Accepted`**:
  ```json
  {
    "document_id": "d1f7b8a0-2f3a-4a2e-8d1e-9f3a4b5c6d7e",
    "file_name": "synthetic_pan.pdf",
    "ocr_status": "PROCESSING",
    "message": "Document uploaded successfully. OCR extraction background job queued."
  }
  ```

---

### Workflow & Human Control Domain (`/api/v1/applications/{id}`)

#### `POST /applications/{id}/nic/approve`
- **Description**: Select and commit 5-digit NIC code.
- **Request Body**:
  ```json
  {
    "nic_suggestion_id": "n1f7b8a0-2f3a-4a2e-8d1e-9f3a4b5c6d7e",
    "override_code_5digit": null
  }
  ```
- **Response `200 OK`**: Updates state to `READY_FOR_PORTAL`.

#### `POST /applications/{id}/automation/start`
- **Description**: Dispatch Playwright worker to automate live portal form.
- **Response `200 OK`**: Updates state to `PORTAL_RUNNING`.

#### `POST /applications/{id}/otp`
- **Description**: Submit OTP code received during portal execution pause.
- **Request Body**:
  ```json
  {
    "otp_code": "123456"
  }
  ```
- **Response `200 OK`**: Updates state to `OTP_VERIFIED` and triggers Playwright resumption.

---

## 3. Standardized Error Payload (RFC 7807)

```json
{
  "type": "https://api.taxla.com/errors/VALIDATION_FAILED",
  "title": "Validation Error",
  "status": 422,
  "detail": "PAN number format is invalid.",
  "instance": "/api/v1/applications",
  "invalid_params": [
    {
      "name": "pan_number",
      "reason": "Value 'INVALID123' does not match pattern ^[A-Z]{5}[0-9]{4}[A-Z]{1}$"
    }
  ]
}
```