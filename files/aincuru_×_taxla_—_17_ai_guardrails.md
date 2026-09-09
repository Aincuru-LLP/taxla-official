# AINCURU × TAXLA — AI GUARDRAILS SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: AI Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. The Zero-Trust Policy

The core rule of Taxla is that **AI outputs are treated as hostile external input**. An LLM outputting `{"pan": "ABCDE1234F"}` does not mean the PAN is valid.

## 2. Layers of Guardrails

### Layer 1: Schema Guardrails (Pydantic)
- Does the output match the JSON schema? Are the types correct? (e.g., Did it return an integer instead of a string?).

### Layer 2: Deterministic Business Rules
- Does the PAN match the regex `^[A-Z]{5}[0-9]{4}[A-Z]{1}$`?
- Does the checksum of the Aadhaar number pass the Verhoeff algorithm?
- If Layer 2 fails, the AI confidence score is irrelevant—the data is marked `INVALID`.

### Layer 3: The Human Guardrail
- AI is strictly prohibited from mutating application state directly or pushing data to the Playwright automation script.
- AI writes to staging tables (`extracted_data`, `nic_suggestions`).
- An authenticated `REVIEWER` or `OPERATOR` must explicitly transition the state.

## 4. Forbidden AI Capabilities

To ensure compliance and safety, the AI runtime environment is physically restricted:
- **No Network Access**: The Ollama LLM container does not have outbound internet access. It cannot leak data or call external webhook APIs.
- **No Direct DB Access**: The LLM cannot execute SQL. It only returns strings.
- **No Secrets**: JWT keys, portal passwords, and API keys are never passed into prompt context.