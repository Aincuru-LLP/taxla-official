# AINCURU × TAXLA — DOCUMENT PROCESSING & OCR SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: AI & Document Engineering
version: 1.1
target_module: MSME / Udyam Registration Engine (V1)
---

## 1. Document Intake Architecture

The Document Ingestion Pipeline processes synthetic identity and financial proof documents uploaded in PDF, PNG, or JPG format. It normalizes images, performs layout detection, runs local OCR, and parses structured entity fields.

```text
[Uploaded File (PDF/PNG/JPG)]
        │
        ▼
[Pre-processing Engine]
  ├── PDF to Image Conversion (300 DPI via pdf2image)
  ├── Image Binarization, Grayscale & Deskewing (OpenCV)
  └── Format Validation & Noise Reduction
        │
        ▼
[OCR Engine (PaddleOCR / Tesseract Fallback)]
  ├── Bounding Box Detection
  ├── Text Recognition & Character Confidence Scoring
  └── Layout Reconstruction
        │
        ▼
[Entity Extraction & Regex Parser]
  ├── Field Parsing (PAN, Aadhaar, Name, Address, IFSC, Account No)
  ├── Regex & Pattern Validation
  └── Confidence Assignment (0.00 - 1.00)
        │
        ▼
[Structured JSON Output & DB Persistence]
```

---

## 2. Extraction Field Schemas & Validation Rules

### PAN Card Extraction (`PAN_CARD`)
- **Target Fields**:
  - `pan_number`: Regex `^[A-Z]{5}[0-9]{4}[A-Z]{1}$`
  - `applicant_name`: Text block preceding DOB / Father's Name.
  - `dob`: Date format `DD/MM/YYYY`.
- **Validation**: PAN checksum structure must be valid. Mandatory upper-case conversion.

### Aadhaar Card Extraction (`AADHAAR_CARD`)
- **Target Fields**:
  - `aadhaar_number`: Regex `^[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}$` (Hashed before DB storage).
  - `applicant_name`: Header block text.
  - `address`: Regex pattern matching PIN code `^[1-9][0-9]{5}$`.
- **Privacy Rule**: Raw Aadhaar number is extracted transiently for portal form filling; stored in DB only as `SHA-256` hash (`aadhaar_number_hash`).

### Bank Statement / Cancelled Cheque (`BANK_PROOF`)
- **Target Fields**:
  - `bank_account_number`: Numeric regex `^[0-9]{9,18}$`.
  - `bank_ifsc`: Regex `^[A-Z]{4}0[A-Z0-9]{6}$`.
  - `bank_name`: Bank institution name.
  - `branch_name`: Branch location text.

---

## 3. OCR Confidence Scoring & Threshold Matrix

| Confidence Metric | System Classification | Action Required |
| :--- | :--- | :--- |
| **0.85 – 1.00** | `HIGH_CONFIDENCE` | Auto-verify field; populate form payload directly. |
| **0.70 – 0.84** | `MEDIUM_CONFIDENCE` | Display field with yellow badge; flag for operator visual verification. |
| **0.00 – 0.69** | `LOW_CONFIDENCE` | Highlight field in red; force operator manual verification on side-by-side UI screen. |

---

## 4. Side-by-Side UI Verification Specs

The Next.js Web UI presents a visual verification component:
1. **Left Canvas**: Interactive document viewer displaying the uploaded PNG/PDF with bounding boxes drawn over detected text zones.
2. **Right Form**: Editable form fields auto-populated with extracted values, confidence indicators, and field-level validation status.
3. **Bounding Box Interactivity**: Clicking a field on the right highlights the corresponding bounding box coordinate on the document image on the left.

## Extraction Principles
- Keep raw OCR separate from canonical fields.
- Store confidence per field.
- Preserve source-document reference.
- Never silently replace user-approved values with later AI output.

## Failure States
Unsupported file, corrupt file, unreadable content, OCR failure, extraction schema failure and low confidence.