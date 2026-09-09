# AINCURU × TAXLA — WORKFLOW ENGINE SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Workflow Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. Workflow Architecture (DAG Model)

The Workflow Engine models processes as Directed Acyclic Graphs (DAGs). For V1, the graph is hardcoded in Python to guarantee deterministic execution, rather than being parsed from a flexible JSON/UI builder.

```text
Workflow Instance
├── application_id (UUID)
├── current_node (String Enum)
├── status (RUNNING | PAUSED | FAILED | COMPLETED)
└── context_json (Aggregate payload of all accumulated data)
```

## 2. Node Execution Contract

Every Node in the workflow must implement a strict contract:
- **`node_key`**: Unique identifier (e.g., `EXTRACT_DOCUMENT`).
- **`input_schema`**: Pydantic model validating data required *before* execution.
- **`execute()`**: Async function performing the work.
- **`output_schema`**: Pydantic model validating the result.
- **`next_node()`**: Function determining the subsequent node based on the output.

## 3. The MSME V1 Node Sequence

1. **`NODE_INIT`**: Triggered by Application Creation.
2. **`NODE_DOCUMENT_UPLOAD`**: Waits for user to upload required files.
3. **`NODE_OCR_EXTRACT`**: Triggers PaddleOCR/Ollama.
4. **`NODE_HUMAN_REVIEW_DATA`**: Pauses for Operator review.
5. **`NODE_PORTAL_SUBMIT`**: Triggers Playwright.
6. **`NODE_OTP_CHECKPOINT`**: Pauses Playwright, waits for OTP via API.
7. **`NODE_FINAL_APPROVAL`**: Reviewer confirms submission.
8. **`NODE_COMPLETE`**: Fetches certificate.

## 4. Execution Integrity & Safety

- **Atomic Transitions**: Moving from `NODE_A` to `NODE_B` must happen in a single database transaction updating `workflows.current_node` and writing to `workflow_events`.
- **No Silenced Errors**: If `execute()` throws an exception, the workflow transitions to `FAILED`. A human must intervene to retry the node.
- **Context Immutability**: `context_json` is an append-only log of accumulated data. Nodes do not overwrite data from previous nodes; they append their specific outputs.