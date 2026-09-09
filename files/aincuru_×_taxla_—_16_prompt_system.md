# AINCURU × TAXLA — PROMPT SYSTEM SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: AI Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Prompt Management

Prompts are treated as code. They must be versioned, reviewed, and stored in a centralized directory, NOT hardcoded randomly inside route handlers.

```text
backend/app/ai/prompts/
├── entity_extraction_v1.jinja
├── nic_classifier_v1.jinja
└── error_correction_v1.jinja
```

## 2. Templating Engine

We use **Jinja2** to render prompts safely. This prevents prompt-injection attacks caused by raw f-string interpolation.

**Example `entity_extraction_v1.jinja`**:
```text
You are a highly precise data extraction system.
Extract the PAN Number and Date of Birth from the following OCR text.
If a field is illegible, return null. Do not guess.

<OCR_TEXT>
{{ ocr_text }}
</OCR_TEXT>

Return ONLY a JSON object matching this schema:
{{ json_schema }}
```

## 3. Mandatory Prompt Requirements

Every prompt template must enforce:
1. **Role Definition**: "You are a highly precise..."
2. **Strict Guardrails**: "Do not guess. Return null if missing."
3. **Format Instruction**: "Return ONLY a JSON object..."
4. **Data Isolation**: User data must be isolated within XML-style tags `<OCR_TEXT>...</OCR_TEXT>` to prevent the model from misinterpreting user data as system instructions.

## 4. Error Correction Prompts

If a model returns invalid JSON, the system uses an `error_correction` prompt, passing the original prompt, the failed output, and the Pydantic validation error:
```text
You previously output invalid JSON. Fix the error below.
Error: {{ pydantic_error }}
Failed Output: {{ failed_output }}
```