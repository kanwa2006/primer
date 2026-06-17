import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        // Verdict palette (keep existing names, fix values for both modes via CSS var)
        positive:      { DEFAULT: "#34d399", dark: "#059669" },
        negative:      { DEFAULT: "#f87171", dark: "#dc2626" },
        "within-noise": { DEFAULT: "#94a3b8", dark: "#475569" },
        refused:        { DEFAULT: "#a1a1aa", dark: "#71717a" },
        // Design system surfaces and text via CSS vars
        surface:   {
          base:     "var(--surface-base)",
          elevated: "var(--surface-elevated)",
          raised:   "var(--surface-raised)",
        },
        border: {
          hairline: "var(--border-hairline)",
          strong:   "var(--border-strong)",
        },
        text: {
          primary:   "var(--text-primary)",
          secondary: "var(--text-secondary)",
          tertiary:  "var(--text-tertiary)",
        },
        accent: {
          signal: "var(--accent-signal)",
        },
      },
      maxWidth: {
        content: "1200px",
        data:    "64rem", // max-w-5xl
      },
      borderRadius: {
        sm:   "6px",
        md:   "8px",
        card: "10px",
        hero: "16px",
      },
      // Machined-surface elevation — layered, low-spread, micro-contrast ring. §V4.4
      boxShadow: {
        card:       "0 1px 0 0 var(--edge-light) inset, 0 0 0 1px var(--shadow-ring), 0 1px 1px rgba(0,0,0,.30), 0 6px 20px -10px rgba(0,0,0,.5)",
        "card-hover":"0 1px 0 0 var(--edge-light-strong) inset, 0 0 0 1px var(--shadow-ring), 0 2px 4px rgba(0,0,0,.4), 0 20px 48px -18px rgba(0,0,0,.62)",
        hero:       "0 1px 0 0 var(--edge-light) inset, 0 0 0 1px var(--shadow-ring), 0 2px 6px rgba(0,0,0,.28), 0 28px 70px -28px rgba(0,0,0,.62)",
        glow:       "0 0 0 1px var(--border-strong), 0 0 24px -6px var(--accent-glow)",
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease forwards",
        "fade-up": "fadeUp 0.4s cubic-bezier(.16,1,.3,1) forwards",
        "count-up": "countUp 0.9s cubic-bezier(.23,1,.32,1) forwards",
      },
      keyframes: {
        fadeIn: {
          "0%":   { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        fadeUp: {
          "0%":   { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        countUp: {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
