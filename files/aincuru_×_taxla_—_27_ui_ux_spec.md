# AINCURU × TAXLA — UI/UX SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Design & Frontend Engineering
version: 1.1
target_module: Frontend UI
---

## 1. Design Language & Aesthetics

Taxla must convey trust, precision, and modern enterprise capability.
- **Color Palette**: Slate/Zinc dark modes, high-contrast whites for documents, with semantic colors (Green/Emerald for Verification, Amber for Human Review, Red/Rose for Rejection).
- **Component System**: Based on `shadcn/ui` and Radix primitives for accessibility.
- **Typography**: Inter or similar clean sans-serif. Monospace fonts for raw data (JSON, Codes, IDs).

## 2. The Application Workspace (The Core Screen)

The Application Workspace is the heart of the system. It uses a **Split-Pane Layout**:

- **Left Pane (Context & Evidence)**: 
  - Displays the uploaded document (PDF/Image Viewer).
  - Highlights specific bounding boxes if supported by OCR.
- **Right Pane (Action & State)**:
  - **Header**: Application ID, Applicant Name, Current Status Badge (e.g., `PAUSED_FOR_REVIEW`).
  - **Body**: The dynamic validation form. Shows Extracted Fields vs Original Fields. Includes AI confidence scores (e.g., "PAN Number: ABCDE1234F [98% Confidence]").
  - **Footer/Sticky Bar**: The primary action buttons ("Approve & Continue", "Reject", "Request OTP").

## 3. Workflow Visibility

Users must never guess what the system is doing.
- **Status Stepper**: A horizontal or vertical timeline showing the 5-Tier workflow progression.
- **Live Terminal (Optional/Debug)**: A collapsible drawer showing real-time WebSocket events from the Playwright worker (e.g., "Navigating to portal...", "Solving captcha...", "Waiting for OTP...").

## 4. State Management Rules

- **Optimistic UI**: Use React Query mutations to optimistically update the UI when an operator approves a field, reverting if the API fails.
- **Empty States**: Never show a blank screen. If there are no applications, show an illustration and a clear CTA to "Create New Application".
- **Loading Skeletons**: Prefer shimmer skeleton loaders over blocking spinner overlays to maintain contextual awareness.