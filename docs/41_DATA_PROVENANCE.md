# 41 — Data Provenance Specification

## 1. Provenance Sources

Every critical data point in TAXLA records explicit origin metadata:

- **`USER_PROVIDED`**: Entered directly by applicant or client in form/questionnaire.
- **`DOCUMENT_EXTRACTED`**: Extracted by local Ollama + Qwen from OCR/parsed text.
- **`GOVERNMENT_DERIVED`**: Derived from official portal verification (e.g. PAN/GSTIN linked data).
- **`AI_DERIVED`**: Inferred by specialized AI agent (e.g. NIC classification suggestions).
- **`SYSTEM_CALCULATED`**: Computed deterministically (e.g. Total Employment = Male + Female + Others).
- **`HUMAN_CORRECTED`**: Edited by operator/reviewer during validation review.
- **`HUMAN_APPROVED`**: Formally signed off by reviewer before portal submission.

## 2. Provenance Record Schema

```json
{
  "field_key": "pan_number",
  "raw_value": "ABCDE1234F",
  "normalized_value": "ABCDE1234F",
  "source": "DOCUMENT_EXTRACTED",
  "confidence": 0.98,
  "document_id": "8f3b2075-8ef6-411a-82ee-098522e8483a",
  "page": 1,
  "location": {"bbox": [120, 45, 230, 60]},
  "method": "QWEN_STRUCTURED_JSON",
  "model": "qwen2.5:3b",
  "model_version": "v1.0.0",
  "prompt_version": "document_extraction_v1",
  "human_verified": false,
  "human_edited": false,
  "timestamp": "2026-09-01T17:30:00Z"
}
```

## 3. Override and Conflict Policy

1. **Government-derived values** take highest priority for statutory checks (cannot be overwritten by AI).
2. **Human-corrected values** take precedence over raw extraction.
3. If competing sources report conflicting values (e.g. Name on Aadhaar vs Name on PAN):
   - A `DATA_CONFLICT` exception is generated.
   - Both sources and confidence levels are displayed side-by-side in the Application Workspace.
   - An operator must manually resolve the conflict.
