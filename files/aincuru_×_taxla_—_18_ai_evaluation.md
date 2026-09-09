# AINCURU × TAXLA — AI EVALUATION SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: AI Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Continuous Evaluation Goal

Because we use local models (Ollama/Qwen/Llama), we must prove they operate at an accuracy level sufficient for enterprise use. Evaluation is not an afterthought; it is a CI/CD requirement.

## 2. Evaluation Datasets

We maintain a static, versioned set of **Synthetic Test Cases** (`tests/ai_eval_data/`):
- **Clean Set**: 50 perfectly legible, synthetic Aadhaar/PAN images.
- **Noisy Set**: 50 skewed, blurry, watermarked, or rotated synthetic documents.
- **NIC Set**: 100 diverse business descriptions ranging from highly specific ("manufacturing rubber gaskets") to highly ambiguous ("doing trade").

## 3. Core Metrics & Thresholds

| Metric | Definition | Target Threshold |
|---|---|---|
| **JSON Parse Rate** | Percentage of outputs that successfully parse into Pydantic on the first try. | > 98% |
| **Extraction Accuracy** | Exact string match for critical fields (PAN, Aadhaar) on the Clean Set. | > 99% |
| **NIC Top-3 Hit Rate** | Does the correct official NIC code appear in the top 3 AI recommendations? | > 90% |
| **Hallucination Rate** | Does the model invent a PAN when the document provided is a blank page? | 0% |
| **P95 Latency** | Time taken for local generation to complete. | < 5000ms |

## 4. The Evaluation Gate

When developers tweak a Jinja2 prompt or switch the local Ollama model (e.g., from Qwen 3B to Llama-3 8B), they MUST run the automated evaluation script (`python scripts/evaluate_ai.py`).
If any Target Threshold is breached, the PR/commit is rejected. Prompt engineering must be regression-tested.