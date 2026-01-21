/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'chat-bg': '#f5f5f5',
        'user-bubble': '#e3f2fd',
        'assistant-bubble': '#f0f0f0',
      },
    },
  },
  plugins: [],
}
