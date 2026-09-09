# AINCURU × TAXLA — AI AGENTS & TASKS SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: AI Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Agent Definition Philosophy

Taxla uses highly specialized "Micro-Agents". These are single-purpose LLM calls rather than autonomous multi-step loops (like AutoGPT). They have no memory, no loop limits, and cannot independently invoke external APIs.

## 2. V1 Agents

### 2.1 Entity Extraction Agent
- **Purpose**: Convert noisy OCR text from Aadhaar/PAN into structured fields.
- **Input**: Raw text string.
- **Output Schema**: 
  ```json
  {"pan_number": "string", "name": "string", "dob": "YYYY-MM-DD", "confidence": "float"}
  ```
- **Forbidden Actions**: Cannot mutate database, cannot execute browser automation.

### 2.2 NIC Classification Agent
- **Purpose**: Read a user's natural language business description (e.g., "I sell handmade soap") and select the top 3 matching NIC 2008 codes.
- **Mechanism**: The backend first runs a semantic vector search to find the top 10 relevant codes, then passes them to the LLM to rerank and extract the exact 5-digit code.
- **Output Schema**: 
  ```json
  {"top_matches": [{"nic_5_digit": "string", "confidence": "float", "rationale": "string"}]}
  ```
- **Forbidden Actions**: Cannot approve the code on behalf of a human.

## 3. Human-in-the-Loop Constraints

Agents are isolated calculators. They return their JSON payload to the Workflow Worker. The Worker persists the output into `extracted_data` or `nic_suggestions` tables, and the workflow state transitions to `PAUSED_FOR_REVIEW`. A human must explicitly click "Approve" in the UI to accept the agent's work.