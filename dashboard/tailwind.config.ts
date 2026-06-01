import type { Config } from "tailwindcss";

const config: Config = {
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
        positive: "#34d399",   // emerald-400
        negative: "#f87171",   // red-400
        "within-noise": "#475569", // slate-600 — calm blue-gray (off amber); AA 7.3:1 on #fafafa
        refused:  "#71717a",   // zinc-500 — muted/desaturated; AA 4.63:1 on #fafafa
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease forwards",
      },
      keyframes: {
        fadeIn: {
          "0%":   { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
