# AINCURU × TAXLA — NIC CLASSIFICATION ENGINE SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: AI & Domain Engineering
version: 1.1
target_module: MSME / Udyam Registration Engine (V1)
---

## 1. Engine Objective & Scope

The National Industrial Classification (NIC 2008) standard is required for Udyam registration in India. Business activities must be mapped accurately down to 2-digit (Division), 4-digit (Group), and 5-digit (Sub-class) codes. The **NIC Classification Engine** accepts free-form business descriptions and automatically ranks the top candidate 5-digit codes with confidence scoring and human override capabilities.

---

## 2. 3-Tier Mapping Algorithm

```text
[Operator / Client Business Description Text]
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ Tier A: Fast Exact & Fuzzy Keyword Match (TF-IDF / SQLite)  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Score < 0.85
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Tier B: Dense Vector Embedding Similarity (Sentence-BERT)   │
│ Embed user text → Cosine similarity against 2008 NIC Index  │
└──────────────────────────────┬──────────────────────────────┘
                               │ Candidate Filtering
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Tier C: Local LLM Contextual Ranker (Ollama / Qwen2.5)     │
│ Analyze nuance, rank top 3 candidates + rationale           │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
[NIC Suggestions Payload → Operator UI for Selection]
```

---

## 3. Ollama Prompt Template & Schema Constraints

```json
{
  "system_prompt": "You are an expert Indian business classifier specializing in the National Industrial Classification (NIC 2008) handbook. Analyze the provided business description and select the top 3 most accurate 5-digit NIC codes.",
  "user_prompt_template": "Business Description: '{business_description}'\nLocation: '{location_text}'\n\nReturn JSON output strictly obeying the following schema:\n{\n  \"suggestions\": [\n    {\n      \"nic_2digit\": \"10\",\n      \"nic_4digit\": \"1071\",\n      \"nic_5digit\": \"10712\",\n      \"description\": \"Manufacture of biscuits, cakes, pastries and other bakery products\",\n      \"confidence\": 0.94,\n      \"rationale\": \"Primary business activity involves commercial production of bakery items.\"\n    }\n  ]\n}",
  "temperature": 0.1,
  "response_format": "json"
}
```

---

## 4. Hierarchy Structure & Example Candidates

### Example Output Data Structure
```json
[
  {
    "rank": 1,
    "nic_2digit": "62",
    "nic_4digit": "6201",
    "nic_5digit": "62011",
    "description": "Writing, modifying, testing of computer program/software to meet the needs of a particular client",
    "confidence": 0.92,
    "rationale": "Matches software development services specified in application input."
  },
  {
    "rank": 2,
    "nic_2digit": "62",
    "nic_4digit": "6202",
    "nic_5digit": "62020",
    "description": "Computer consultancy and computer facilities management activities",
    "confidence": 0.78,
    "rationale": "Related IT consulting services provided by enterprise."
  }
]
```

---

## 5. Human-in-the-Loop Override Rules

1. **Mandatory Checkpoint**: Automation CANNOT proceed to `READY_FOR_PORTAL` until an operator or reviewer explicitly clicks "Confirm NIC Selection" in the UI.
2. **Custom Search & Override**: If the AI suggestions are incomplete, the operator can type a custom query into a searchable NIC 2008 dropdown component in the UI to select any official code.
3. **Audit Trail**: If an operator overrides the rank-1 AI suggestion, the system records the AI recommendation, the operator's choice, and the timestamp in `nic_suggestions` and `audit_logs`.

## Failure
No candidate, ambiguous description, low confidence or missing business activity must route to review.