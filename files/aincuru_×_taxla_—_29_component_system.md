# AINCURU × TAXLA — COMPONENT SYSTEM SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Frontend Engineering
version: 1.1
target_module: Frontend UI
---

## 1. Core Philosophy (shadcn/ui)

Taxla does not use heavy component libraries like Material-UI. It uses **shadcn/ui** (Radix primitives + Tailwind). Components are owned by our codebase (`components/ui/*`), not a node_module, allowing infinite customization.

## 2. Component Hierarchy (Atomic Design)

### Primitives (Atoms)
- `Button`, `Input`, `Badge`, `Checkbox`, `Skeleton`, `Tooltip`.
- *Rule*: Absolutely zero business logic or API calls here. Strictly presentational.

### Molecules
- **`StatusBadge`**: Maps `application.status` to a colored badge with an icon.
- **`ConfidenceIndicator`**: A small progress bar mapping an LLM's `0.0 - 1.0` confidence to Red/Yellow/Green.
- **`DataField`**: A label, input, and validation state wrapper.

### Organisms (Domain Specific)
- **`DocumentViewer`**: Renders PDF/Images with zoom/pan capabilities.
- **`ExtractedDataForm`**: Wraps multiple `DataField`s with React Hook Form, handling the mutation logic to update `extracted_data`.
- **`WorkflowStepper`**: Reads the `workflow_events` array and renders a vertical, animated timeline.

## 3. Strict Development Rules

- **Prop Typing**: Every component MUST define a TypeScript interface for its props. No `any`.
- **Client vs Server**: In Next.js App Router, default to Server Components. Only add `"use client"` when state (`useState`), effects (`useEffect`), or event listeners (`onClick`) are strictly required.
- **Avoid Prop Drilling**: If a component needs deep state, use a Zustand store or React Query hook rather than passing props down 5 levels.