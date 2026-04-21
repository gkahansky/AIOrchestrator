# Design System Strategy: The Architectural Curator

## 1. Overview & Creative North Star
The Creative North Star for this design system is **"The Architectural Curator."** 

In a world of cluttered, "boxy" admin dashboards, this system seeks to establish authority through restraint. We are moving away from the "Bootstrap aesthetic" toward a high-end editorial experience. This is achieved by treating the interface not as a grid of containers, but as a series of curated, layered planes. 

We utilize **intentional asymmetry**—such as offset typography in headers and varying card widths—to guide the eye naturally. By leveraging a sophisticated tonal palette and expansive white space, we transform a functional B2B tool into a premium workspace that feels breathable, intentional, and high-performance.

---

## 2. Colors: Tonal Architecture
The palette is built on the logic of light and depth. We move beyond "blue and gray" into a spectrum of cool neutrals and authoritative accents.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders for sectioning or containment. Structural boundaries must be defined solely through background color shifts or tonal transitions.
*   *Example:* A sidebar using `surface-container-low` (#f3f4f5) sitting against a main content area of `surface` (#f8f9fa).

### Surface Hierarchy & Nesting
Treat the UI as physical layers. Use the following tiers to define importance:
- **Level 0 (Base):** `surface` (#f8f9fa) — The infinite canvas.
- **Level 1 (Sections):** `surface-container-low` (#f3f4f5) — Large structural areas (Sidebar/Top Nav).
- **Level 2 (Cards):** `surface-container-lowest` (#ffffff) — Actionable content pieces.
- **Level 3 (Pop-overs):** `surface-bright` (#f8f9fa) — Floating elements requiring focus.

### The "Glass & Gradient" Rule
To inject "soul" into the professional environment:
- **Glassmorphism:** Use `surface-container-lowest` with 80% opacity and a `24px` backdrop-blur for floating search bars and modal headers.
- **Signature Gradients:** Main Action CTAs should use a subtle linear gradient from `primary` (#003d9b) to `primary-container` (#0052cc) at a 135-degree angle. This provides a tactile, "pressable" depth that flat hex codes lack.

---

## 3. Typography: Editorial Authority
We pair the structural precision of **Inter** with the expressive, wide-set nature of **Manrope** to create an editorial hierarchy.

- **Display & Headlines (Manrope):** Used for "Momentum" areas. Large, bold, and slightly tracking-tight (-0.02em). These aren't just titles; they are statements of intent.
- **Body & Labels (Inter):** Used for "Information" areas. Inter’s tall x-height ensures readability in dense data tables and chat interfaces.

**Hierarchy Strategy:** 
- Use `headline-lg` (32px Manrope) for page titles to establish an immediate focal point.
- Use `label-sm` (11px Inter, All Caps, +5% letter spacing) for metadata and status headers to provide a "technical" contrast to the soft editorial headlines.

---

## 4. Elevation & Depth: Tonal Layering
Traditional shadows are often a crutch for poor layout. In this system, depth is earned through layering and ambient light.

- **The Layering Principle:** Stack `surface-container` tiers. A `surface-container-lowest` (White) card placed on a `surface-container-low` (Light Gray) background creates a natural lift.
- **Ambient Shadows:** For floating elements (e.g., active dropdowns), use a multi-layered "Soft Shadow":
    - `0px 4px 20px rgba(0, 61, 155, 0.04)`
    - `0px 12px 40px rgba(25, 28, 29, 0.06)`
    - This creates a glow rather than a dark smudge.
- **The "Ghost Border" Fallback:** If accessibility requires a stroke (e.g., in high-contrast modes), use `outline-variant` (#c3c6d6) at **15% opacity**.

---

## 5. Components: The Signature Suite

### Buttons: High-Contrast Interaction
- **Primary:** Gradient fill (`primary` to `primary-container`), `on-primary` text. Use `rounded-md` (0.375rem).
- **Secondary (Outlined):** Use the "Ghost Border" logic. A 1px stroke of `outline-variant` at 40% opacity. 
- **Tertiary:** Pure text with `primary` color, but with a subtle `surface-container-high` background on hover.

### Cards & Lists: The Separation Principle
**Rule:** No dividers. 
- Use vertical white space (32px or 48px) to separate list items. 
- For "Agent" or "Data" cards, use a `surface-container-lowest` background with a subtle 4px `primary` accent bar on the left for "Active" states.

### Sidebar & Navigation
- **Active State:** Do not just change the icon color. Use a "Pill" background (`primary-fixed`) with a `primary` text color. The icon should transition from `on-surface-variant` to `primary`.
- **Vertical Spacing:** Use generous padding (12px Y-axis) to ensure the navigation feels like a high-end menu, not a file directory.

### Chat Interface
- **User Bubbles:** `primary` fill, `on-primary` text, `rounded-xl` with the bottom-right corner sharpened (`rounded-none`).
- **AI/Agent Bubbles:** `surface-container-high` fill, `on-surface` text, `rounded-xl` with the bottom-left corner sharpened.
- **Input Field:** `surface-container-lowest` background with a "Ghost Border." The focus state should utilize a 2px outer glow of `primary_fixed_dim` at 50% opacity.

---

## 6. Do's and Don'ts

### Do:
- **Do** use `surface-container` tiers to create hierarchy.
- **Do** allow content to "breathe." If you think there's enough white space, add 16px more.
- **Do** use `Manrope` for all numerical data in cards to give it a "financial boutique" feel.
- **Do** use `rounded-full` for status indicators (Success/Pending) to make them feel like polished gems.

### Don't:
- **Don't** use 100% black (#000000) for text. Use `on-surface` (#191c1d).
- **Don't** use hard, 1px borders between sidebar items or table rows.
- **Don't** use default browser focus rings. Use the custom "Ghost Border" glow.
- **Don't** cram cards together. Use the `xl` (0.75rem) corner radius to ensure shapes feel organic and soft.