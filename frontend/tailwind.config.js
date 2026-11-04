/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        herb: {
          bg: "#F8FAF8",
          primary: "#166534",
          accent: "#16A34A",
          text: "#1F2937",
          border: "#DCE5DF",
        },
      },
      fontFamily: {
        sans: ["'Plus Jakarta Sans'", "'Inter'", "system-ui", "-apple-system", "sans-serif"],
        serif: ["'Georgia'", "'Cambria'", "serif"],
        mono: ["'Consolas'", "'Courier New'", "monospace"],
      },
    },
  },
  plugins: [],
};
