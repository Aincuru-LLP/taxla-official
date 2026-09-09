# Phase 02 — Real OCR Pipeline

**Goal:** Replace the hardcoded `mock_ocr_text` in `backend/worker/ocr_worker.py:57-60` with a real OCR call. End state: uploaded PDFs and images actually go through OCR; per-field confidence scores + bounding boxes flow into the `ExtractedData` table.

---

## Pre-requisites

Phase 01 complete (config & security fixes landed).

---

## Scope (in)

1. **Real OCR worker** — `backend/worker/ocr_worker.py`. Replace lines 57-60 with actual OCR. Use **pytesseract** as the cross-platform default (works on Windows AND Linux). Keep PaddleOCR as a Linux-only fast path (already gated by `sys_platform != "win32"` in `requirements.txt:14-15`).
2. **Input handling** — accept both PDF (`pdf2image` at 300 DPI, already in requirements) and image (PNG/JPG via PIL, already in requirements). Use `opencv-python-headless` for deskew + binarize preprocessing.
3. **Per-field confidence** — Tesseract returns word-level confidences via `image_to_data`. Aggregate to field-level using the regex parsers you already need (PAN: `^[A-Z]{5}\d{4}[A-Z]$`, Aadhaar: `^\d{4}\s\d{4}\s\d{4}$`, IFSC: `^[A-Z]{4}0[A-Z0-9]{6}$`, etc.). If you don't have parsers yet, start with a `RawOcrResult` table that stores lines + confidences, and parse in `ai_extractor.py` (which already exists and is wired to Ollama).
4. **Bounding boxes** — store as JSON in `extracted_data.bounding_box_json` (column already exists; the LLM extraction step currently doesn't populate it). Pull from Tesseract's `left`, `top`, `width`, `height` for the matched word(s).
5. **Error handling** — if OCR fails (Tesseract binary missing, PDF corrupt), mark `documents.ocr_status = "FAILED"`, transition to `EXCEPTION` with `error_code = "OCR_FAILURE"`. Keep the existing try/except shape.

---

## Scope (out)

- Do NOT modify `ai_extractor.py` (the LLM extraction layer is already real; it just gets better input now).
- Do NOT change `validation_engine.py` — that's Phase 04.
- Do NOT add new tables or migrations.
- Do NOT touch the frontend.

---

## Deliverables checklist

- [ ] `backend/worker/ocr_worker.py` — replaces mock text with real OCR call; `RawOcrResult`-style intermediate struct or directly populate `ExtractedData`.
- [ ] New helper: `backend/app/services/ocr_service.py` — wraps pytesseract + pdf2image + cv2 preprocessing. Exposes `extract_text(file_path: str, doc_type: str) -> list[OcrLine]` where `OcrLine = {text, confidence, bbox}`.
- [ ] `backend/requirements.txt` — confirm `pytesseract` is listed (it is, line 16). Note in README that **Tesseract binary must be installed separately** (not pip-installable): `apt install tesseract-ocr` (Linux), `brew install tesseract` (macOS), or download from UB-Mannheim for Windows.
- [ ] `backend/README.md` — document Tesseract install step + where to drop test docs (`backend/storage/documents/`).
- [ ] `backend/tests/test_ocr_pipeline.py` — extend existing test to assert real OCR output for a known fixture (use a small synthetic PNG with a known PAN number).

---

## Verification steps

1. Install Tesseract binary if not already: `tesseract --version`.
2. Place a test PNG in `backend/storage/documents/test_pan.png` (or use the existing test fixture).
3. `cd backend && .venv\Scripts\activate`
4. `python -c "from app.services.ocr_service import OcrService; print(OcrService().extract_text('storage/documents/test_pan.png', 'PAN'))"`
5. Should print a list of OcrLine objects with text, confidence 0-100, and bbox dicts.
6. Upload a real doc via the API: `curl -X POST http://127.0.0.1:8000/api/v1/applications/{id}/documents -F "file=@test.png" -F "type=PAN" -H "Authorization: Bearer $TOKEN"`.
7. Check the database: `ExtractedData` rows should have real `field_value`, `confidence` (Numeric 0-1), and populated `bounding_box_json`.
8. `pytest backend/tests/test_ocr_pipeline.py -v` — passes.

---

## Definition of done

- A real uploaded document goes through actual OCR (not hardcoded text).
- Per-field confidence flows into `extracted_data.confidence` (0-1).
- Bounding boxes flow into `extracted_data.bounding_box_json`.
- OCR failures are caught + reported via `EXCEPTION` state with `OCR_FAILURE` code.
- Tesseract binary install is documented.
- Test fixture + test passes.

---

## CONTINUATION PROMPT — start Phase 03

```
Starting Phase 03 of the AINCURU × TAXLA remediation. Phase 02 is complete:
- Real OCR is wired (pytesseract default; PaddleOCR Linux fast-path).
- PDF (pdf2image @ 300 DPI) and image (PIL) inputs both handled.
- OpenCV deskew + binarize preprocessing in place.
- Per-field confidence (0-1) + bounding boxes (JSON) flow into extracted_data.
- ocr_status=FAILED + EXCEPTION transition with OCR_FAILURE error_code on errors.
- Tesseract binary install documented in backend/README.md.
- New app/services/ocr_service.py wraps the OCR call.
- backend/tests/test_ocr_pipeline.py extended with a real fixture; passes.

Read the full plan: documents/implementation phases/phase-03-workflow-engine.md

Goal: Make the workflow engine actually do something.
1. Extend state_machine.transition() so it ALSO writes a WorkflowEvent row AND updates
   Workflow.current_node + Workflow.status (currently it only updates Application.status
   and writes AuditLog).
2. Add the missing states to VALID_TRANSITIONS: AADHAAR_OTP, PAN_VERIFICATION,
   DATA_VERIFICATION, REGISTERED, DUPLICATE_PAN_DETECTED, UAM_NOT_FOUND. Decide their
   legal predecessors/successors from input requirmentsv2.md §39 (state machine diagram).
3. Remove the RESUME bypass in app/core/state_machine.py:53 — replace with an explicit
   resume_target field on the EXCEPTION transition (so recovery is auditable, not "any
   state").
4. Replace worker/playwright_agent.py:99-111's direct app.status mutation with a proper
   transition() call. Remove the silent try/except: pass.

After Phase 03 verification passes, paste the Phase 04 continuation prompt below.

---

PHASE 04 CONTINUATION PROMPT:

Starting Phase 04 of the AINCURU × TAXLA remediation. Phase 03 is complete: the
workflow engine now writes WorkflowEvent rows + updates Workflow.current_node on every
transition. The 6 missing states are added to VALID_TRANSITIONS. The RESUME bypass is
replaced with an explicit resume_target. The Playwright worker's exception handler
goes through transition() now.

Read the full plan: documents/implementation phases/phase-04-validation-engine.md

Goal: Make validation_engine.py actually branch on confidence per documents/19_document_processing.md:
- HIGH (>=0.85): auto-verify, skip human review, transition VALIDATION -> NIC_REVIEW.
- MEDIUM (0.70-0.84): yellow flag, transition VALIDATION -> VALIDATION_REVIEW
  (notify reviewer but allow override).
- LOW (<0.70): force manual review, transition VALIDATION -> HUMAN_REVIEW_REQUIRED.
Add the new states to the state machine (VALIDATION_REVIEW, HUMAN_REVIEW_REQUIRED).
The validation_rules dict should actually validate PAN format, Aadhaar format, IFSC
format, GSTIN format, mobile (10-digit), email, pincode (6-digit).
```