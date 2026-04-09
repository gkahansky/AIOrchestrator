import type { Config } from "tailwindcss"

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── Design system: "The Architectural Curator" ─────────────────────────
        "primary":                    "#003d9b",
        "primary-container":          "#0052cc",
        "on-primary":                 "#ffffff",
        "on-primary-container":       "#c4d2ff",
        "primary-fixed":              "#dae2ff",
        "primary-fixed-dim":          "#b2c5ff",
        "on-primary-fixed":           "#001848",
        "on-primary-fixed-variant":   "#0040a2",

        "secondary":                  "#525f73",
        "secondary-container":        "#d6e3fb",
        "on-secondary":               "#ffffff",
        "on-secondary-container":     "#586579",
        "secondary-fixed":            "#d6e3fb",
        "secondary-fixed-dim":        "#bac7de",
        "on-secondary-fixed":         "#0f1c2d",
        "on-secondary-fixed-variant": "#3b485a",

        "tertiary":                   "#7b2600",
        "tertiary-container":         "#a33500",
        "on-tertiary":                "#ffffff",
        "on-tertiary-container":      "#ffc6b2",
        "tertiary-fixed":             "#ffdbcf",
        "tertiary-fixed-dim":         "#ffb59b",
        "on-tertiary-fixed":          "#380d00",
        "on-tertiary-fixed-variant":  "#812800",

        "surface":                    "#f8f9fa",
        "surface-bright":             "#f8f9fa",
        "surface-dim":                "#d9dadb",
        "surface-variant":            "#e1e3e4",
        "surface-container-lowest":   "#ffffff",
        "surface-container-low":      "#f3f4f5",
        "surface-container":          "#edeeef",
        "surface-container-high":     "#e7e8e9",
        "surface-container-highest":  "#e1e3e4",
        "surface-tint":               "#0c56d0",

        "on-surface":                 "#191c1d",
        "on-surface-variant":         "#434654",
        "inverse-surface":            "#2e3132",
        "inverse-on-surface":         "#f0f1f2",
        "inverse-primary":            "#b2c5ff",

        "background":                 "#f8f9fa",
        "on-background":              "#191c1d",

        "outline":                    "#737685",
        "outline-variant":            "#c3c6d6",

        "error":                      "#ba1a1a",
        "error-container":            "#ffdad6",
        "on-error":                   "#ffffff",
        "on-error-container":         "#93000a",
      },
      borderRadius: {
        DEFAULT: "0.125rem",
        lg: "0.25rem",
        xl: "0.5rem",
        "2xl": "0.75rem",
        full: "9999px",
      },
      fontFamily: {
        headline: ["Manrope", "sans-serif"],
        body:     ["Inter", "sans-serif"],
        label:    ["Inter", "sans-serif"],
      },
      boxShadow: {
        float:   "0px 4px 20px rgba(0,61,155,0.04), 0px 12px 40px rgba(25,28,29,0.06)",
        card:    "0px 2px 8px rgba(25,28,29,0.05)",
      },
    },
  },
  plugins: [],
}

export default config
