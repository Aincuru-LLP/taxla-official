# AINCURU × TAXLA — UDYAM PORTAL AUTOMATION SPECIFICATION

---
status: APPROVED SPECIFICATION

| Error Type | Trigger | Recovery Mechanism |
| :--- | :--- | :--- |
| **DOM Element Timeout** | Selector missing after 15s | Capture full-page screenshot to `/storage/errors/`; mark state as `EXCEPTION` (`DOM_TIMEOUT`); log failure trace. |
| **Portal Validation Error** | Mock portal throws field error | Parse error text from `.alert-danger`; populate `error_log` in `portal_sessions`; alert operator. |
| **Worker Disconnection** | Redis worker crash | Worker heartbeat checks reset task; state resets to last saved checkpoint (`STEP_1_OTP_WAIT`). |

---

## 4. UI Screenshot Streaming & Real-Time Inspection

- Playwright captures JPEG screenshots at key step completions or during OTP waiting.
- Screenshots are pushed via FastAPI WebSockets to the Next.js Operator Dashboard.
- Operators view live visual feedback of the Playwright browser state directly inside the application workspace.