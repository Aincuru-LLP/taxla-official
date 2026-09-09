# AINCURU × TAXLA — AUTOMATION ENGINE SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Automation Engineering
version: 1.1
target_module: Core Infrastructure
---

## 1. The Automation Model

The Automation Engine is responsible for executing rigid, predefined sequences of actions. It is not a generic rule engine; it is a highly specialized runner for compliance workflows.

```text
Automation Context
├── Trigger (e.g., Document Uploaded, OTP Submitted)
├── Input Payload (Validated by Pydantic)
├── State Preconditions (Checked before execution)
├── Execution Steps (Synchronous logic + Async Workers)
├── Retry Policy (Exponential backoff for transient errors)
├── Checkpoint Strategy (Where to pause)
└── Final Output (State mutation or next trigger)
```

## 2. Playwright Execution Context

The most complex automation is browser manipulation.
- **Stateless Runners**: Every Playwright worker must spin up a fresh browser context or attach to an existing session strictly managed via `PortalSession` records.
- **Headless Mode**: Always headless in production/demo, but supports tracing and screenshot streams to the UI.
- **DOM Resilience**: Prefer robust selectors (`data-testid`, text locators) over fragile XPath. 
- **Timeouts**: Every Playwright action must have an explicit timeout (default 30s) to prevent frozen workers.

## 3. Checkpointing & Human Pauses

When a Playwright automation reaches a CAPTCHA or OTP field:
1. **Pause**: The script evaluates the DOM, detects the required human input.
2. **Snapshot**: Captures a screenshot and saves it to local storage.
3. **Notify**: Emits an event to the `workflow_events` table and pushes a WebSocket notification to the UI.
4. **Sleep**: The worker loop sleeps and polls Redis for an OTP payload, or suspends entirely and relies on the HTTP API to wake it up via a continuation webhook.

## 4. Failure Classification & Recovery

- **Transient Failures (Retryable)**: Network timeouts, 502 Bad Gateway from the portal, element temporarily obscured. *Action: Exponential backoff.*
- **Terminal Failures (Human Escalation)**: Invalid Credentials, Portal structurally changed, Max retries exceeded. *Action: Mark `status=FAILED`, alert Operator.*