# AINCURU × TAXLA — DEMO SCENARIOS SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Product
version: 1.1
target_module: Product Scenarios
---

## 1. Scenario A: The Happy Path (Speed & Automation)
**Goal**: Show how Taxla reduces a 30-minute manual task to 2 minutes.
1. Log in as Operator. Create Application.
2. Upload perfect synthetic Aadhaar and PAN.
3. Show the UI parsing the data in real-time. Click "Approve All".
4. Enter business description: "Software consulting". See NIC `62020` suggested instantly.
5. Click "Start Automation". The screen splits, showing a live Viewport of Playwright filling out the Real Udyam Portal.
6. The portal asks for an OTP. The UI prompts the user. User types `123456`.
7. Playwright resumes, submits, and the certificate is generated.

## 2. Scenario B: The AI Guardrail (Safety & Review)
**Goal**: Prove the system is safe and doesn't hallucinate bad data into production.
## Demo Rules
- Synthetic data only.
- Real portal only.
- Keep the browser automation visible.
1. Upload a blurry, watermarked synthetic Aadhaar where the Date of Birth is illegible.
2. The AI Extraction Agent attempts extraction but fails confidence checks.
3. The UI highlights the `DOB` field in Amber.
4. The Operator manually types the correct DOB.
5. The system logs the manual override in the `audit_logs` and proceeds safely.

## 3. Scenario C: Concurrency (Scale)
**Goal**: Show that the system can handle bulk operations without blocking.
1. Operator selects 3 applications and triggers "Start Automation".
2. The Worker Dashboard shows 3 headless browsers spinning up simultaneously.
3. Two hit OTP barriers and suspend (freeing resources). The third completes.
4. Operator fulfills the OTPs asynchronously, and the paused workers resume.