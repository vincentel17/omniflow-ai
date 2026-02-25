import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      borderRadius: {
        xl: "14px",
        "2xl": "16px",
        "3xl": "20px"
      },
      colors: {
        bg: "rgb(var(--bg) / <alpha-value>)",
        fg: "rgb(var(--foreground) / <alpha-value>)",
        card: "rgb(var(--card) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        ring: "rgb(var(--ring) / <alpha-value>)",
        primary: "rgb(var(--primary) / <alpha-value>)",
        gold: "rgb(var(--accent-gold) / <alpha-value>)",
        orange: "rgb(var(--accent-orange) / <alpha-value>)",
        teal: "rgb(var(--accent-teal) / <alpha-value>)"
      },
      boxShadow: {
        card: "0 8px 26px -16px rgba(15, 23, 42, 0.42), 0 2px 8px rgba(124, 58, 237, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
