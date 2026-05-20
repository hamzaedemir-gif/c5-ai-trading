/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // dark game / terminal palette
        bg: "#0a0e17",
        panel: "#10172a",
        panel2: "#162033",
        border: "#1f2a44",
        accent: "#00ff88",
        accent2: "#00ffe0",
        warn: "#ffd166",
        danger: "#ff4d6d",
        green: "#00ff88",
        red: "#ff4d6d",
        mute: "#5a6b8f",
        text: "#e6edf7",
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "'Fira Code'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 12px rgba(0, 255, 136, 0.35)",
      },
      keyframes: {
        flashUp: {
          "0%": { backgroundColor: "rgba(0, 255, 136, 0.35)" },
          "100%": { backgroundColor: "transparent" },
        },
        flashDown: {
          "0%": { backgroundColor: "rgba(255, 77, 109, 0.35)" },
          "100%": { backgroundColor: "transparent" },
        },
      },
      animation: {
        flashUp: "flashUp 0.8s ease-out",
        flashDown: "flashDown 0.8s ease-out",
      },
    },
  },
  plugins: [],
};
