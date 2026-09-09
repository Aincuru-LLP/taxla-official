# AINCURU × TAXLA — DESIGN SYSTEM SPECIFICATION

---
status: APPROVED SPECIFICATION
owner: Design & Frontend Engineering
version: 1.1
target_module: Frontend UI
---

## 1. Visual Aesthetics & Vibe

Taxla is designed to WOW the user through a sense of premium, dynamic enterprise capability.
- **Vibrant & Dark**: The UI relies on a sleek dark mode (slate/zinc) contrasted by vibrant semantic accents (emerald, violet, amber). Avoid generic, flat colors.
- **Glassmorphism**: Use subtle transparency and background blur for overlays, sticky headers, and command palettes to create depth.

## 2. Tailwind Tokens & Styling Rules

All styling must use Tailwind classes. Do not write custom CSS unless implementing a complex animation impossible in Tailwind.

- **Typography**: Inter (sans) for UI, Fira Code or JetBrains Mono for data points. `tracking-tight` on headings.
- **Borders**: `border-border` with `rounded-xl` or `rounded-2xl` for cards to soften the enterprise feel.
- **Shadows**: Soft, multi-layered shadows (`shadow-lg shadow-black/20`).

## 3. Dynamic Interaction & Micro-Animations

A static UI is a dead UI.
- **Hover States**: Every interactive element must respond to hover (scale up `hover:scale-105`, brightness change, or subtle border glow).
- **Transitions**: Use `transition-all duration-200 ease-in-out` as the baseline.
- **Loading**: Use animated gradient shimmers instead of static gray blocks.
- **Success/Fail**: When a workflow step completes, use a micro-animation (e.g., a checkmark drawing itself or a subtle pulse).

## 4. Accessibility (A11y)

- **Contrast**: Text must pass WCAG AA.
- **Focus Rings**: Never remove `focus-visible:ring`. Customize it to match the brand color.