# AINCURU × TAXLA — AI ARCHITECTURE SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: AI Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. AI Pipeline & Strict Validation

The AI pipeline is designed to convert unstructured real-world ambiguity into structured, predictable data. AI output is intrinsically untrusted until it passes deterministic business validation.

```text
Input (PDF / Text)
→ OCR Engine (PaddleOCR)
→ Prompt Injection
→ Local LLM (Ollama)
→ Structured Output (JSON Response Format)
→ Schema Validation (Pydantic models)
→ Deterministic Validation (Regex, checksums like PAN/Aadhaar formats)
→ UI Escalation (Human Operator Review)
```

## 2. V1 AI Capabilities & Models

To maintain complete data privacy and zero API costs for development/demo:
- **Optical Character Recognition**: `PaddleOCR` (English/Hindi models). Handles slanted, skewed Indian identity documents better than raw Tesseract.
- **Language Model**: `Qwen2.5:3b` or `Llama-3-8B-Instruct` running locally via **Ollama**. Chosen for high capability in zero-shot JSON extraction and reasoning on small VRAM (8GB-16GB).
- **Semantic Search (NIC Codes)**: `all-MiniLM-L6-v2` (SentenceTransformers) for fast embedding search against the NIC 2008 dataset.

## 3. Structured Output & Guardrails

The system does NOT use conversational AI wrappers (like LangChain chat memory). It uses raw API calls to the LLM with strict instructions to output JSON.
- If the output fails `Pydantic` parsing, the system executes exactly 2 automated retries with an error-correction prompt.
- If it fails again, the state transitions to `AI_FAILED` and alerts a human.

## 4. Observability & Auditing

Every LLM call logs:
- `model_name` and `version`
- `prompt_template_id`
- `latency_ms`
- `token_count` (Input/Output)
- `validation_status` (Pass/Fail)
*(Note: Raw PII inputs are NOT logged to Prometheus, only execution metadata).*