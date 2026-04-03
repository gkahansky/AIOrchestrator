```markdown
# Design System Specification: Architectural Precision

## 1. Overview & Creative North Star
The Creative North Star for this design system is **"The Digital Architect."** 

Moving away from the generic, bubbly aesthetic of consumer SaaS, this system adopts an "Industrial-Editorial" lens. It prioritizes high-density information through a sophisticated, structured layout that mimics the blueprints of high-end infrastructure. We break the "template" look by utilizing intentional white space (the "Silent Grid") and high-contrast typographic scales. The UI doesn’t just sit on the screen; it is built into it through layered tonal depths and glass-like surfaces, creating a focused environment for high-stakes decision-making.

---

## 2. Colors: Tonal Logic over Structural Lines
Our palette is rooted in professional slate and charcoal, punctuated by high-chroma semantic signals.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders for sectioning or layout containment. 
Boundary definition must be achieved through:
1. **Background Shifts:** Placing a `surface-container-low` component on a `surface` background.
2. **Negative Space:** Using the Spacing Scale to create "gutters" of light.
3. **Tonal Transitions:** Subtle shifts between nested containers to imply hierarchy.

### Surface Hierarchy & Nesting
Treat the UI as a series of stacked architectural plates.
- **Base Layer:** `surface` (#faf8ff) for the main application canvas.
- **Secondary Workspaces:** `surface-container-low` (#f2f3ff) for sidebars or utility panels.
- **Primary Content Cards:** `surface-container-lowest` (#ffffff) to provide the highest "lift" and cleanest reading surface.
- **Nested Accents:** Use `surface-container-high` (#e2e7ff) only for small, inset data modules or "well" states within cards.

### The "Glass & Gradient" Rule
To elevate the "infra" feel, floating elements (modals, dropdowns, hovering tooltips) should utilize **Glassmorphism**.
- **Fill:** `surface_variant` at 70% opacity.
- **Effect:** `backdrop-filter: blur(12px)`.
- **CTA Soul:** Main actions should use a subtle linear gradient from `primary` (#0056c6) to `primary_container` (#006df8) at a 135-degree angle to add a "lithographic" depth that flat color cannot replicate.

---

## 3. Typography: The Editorial Engine
We pair **Manrope** (Display/Headlines) with **Inter** (UI/Data) to balance architectural character with technical legibility.

- **Display & Headlines (Manrope):** Use these for high-level infrastructure metrics and page titles. The wide apertures of Manrope convey authority and modernism.
- **Title & Body (Inter):** The workhorse. Inter’s tall x-height ensures that dense tabular data remains readable even at `body-sm` (0.75rem).
- **Label (Inter):** Used for metadata and status badges. Always set in `Medium` or `Semi-Bold` weight to maintain high contrast against tonal backgrounds.

---

## 4. Elevation & Depth: Tonal Layering
We reject the heavy drop-shadows of the 2010s. Depth is a product of light and material density.

- **The Layering Principle:** Instead of shadows, stack your tokens. A `surface-container-lowest` card sitting on a `surface-container-low` background creates a natural, crisp "lift."
- **Ambient Shadows:** If a component *must* float (e.g., a Command Palette), use an ambient shadow: `0px 20px 40px rgba(19, 27, 46, 0.06)`. Note the use of the `on-surface` color (#131b2e) for the shadow tint rather than pure black.
- **The "Ghost Border" Fallback:** For high-density data tables where separation is critical, use a "Ghost Border": `outline-variant` (#c2c6d8) at **15% opacity**. It should be felt, not seen.

---

## 5. Components: Industrial primitives

### Buttons: The Tactile Command
- **Primary:** Gradient fill (`primary` to `primary_container`), `DEFAULT` (4px) corner radius. Text: `label-md` in `on_primary`.
- **Secondary:** Surface-only. `surface-container-highest` background with `on_surface` text. No border.
- **Tertiary:** `Ghost` style. No background; text color is `primary`. Underline only on hover.

### Dense Data Tables
- **Zebra Striping:** Use `surface-container-low` for even rows; `surface-container-lowest` for odd.
- **Forbid Dividers:** Horizontal lines are replaced by 0.4rem (`2`) vertical padding.
- **Typography:** Tabular figures (monospaced numbers) must be enabled for all data columns to ensure decimal alignment.

### Status Badges (Semantic Architecture)
Badges are not "bubbly" pills; they are architectural markers.
- **Shape:** `sm` (2px) corner radius.
- **Colors:**
    - **Production:** `primary` background / `on_primary` text.
    - **Success:** Emerald Green tint.
    - **Review:** `tertiary_container` / `on_tertiary_fixed_variant`.
    - **Failed:** `error` / `on_error`.

### Cards & Layout Containers
- **Padding:** Always use `spacing-5` (1.1rem) or `spacing-6` (1.3rem) for internal card padding to allow data to "breathe."
- **Rounding:** Strictly `md` (0.375rem / 6px) for standard cards; `lg` (0.5rem / 8px) for major layout containers.

---

## 6. Do’s and Don’ts

### Do:
- **Use Asymmetric Grids:** Allow the sidebar or a "Summary Rail" to take up non-standard widths (e.g., 18% vs 82%) to break the "Bootstrap" look.
- **Prioritize Data Density:** Use `body-sm` for table content but maintain generous cell padding.
- **Embrace White Space:** Use `spacing-16` (3.5rem) between major sections to define the "Digital Architecture."

### Don’t:
- **Don’t use 100% Black:** Always use `on_surface` (#131b2e) for text to maintain a premium, slate-toned aesthetic.
- **Don’t use "Bubbly" Corners:** Avoid `full` (pill) rounding on anything other than status chips. Buttons and cards must feel "constructed."
- **Don’t use Dividers:** If you feel the need to add a line, try adding `0.5rem` of space or a 2% tonal shift instead. 1px lines are a failure of spatial layout.

---

## 7. Signature Infrastructure Component: The "Pulse Monitor"
For this infra-focused system, we introduce the **Pulse Monitor**. This is a condensed, sparkline-based card used for real-time monitoring. It uses a `surface_container_lowest` background with a subtle `primary` glow (using a 5% opacity `primary` shadow) to indicate an "Active" system state without using aggressive animations.```