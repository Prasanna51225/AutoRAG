/** @type {import('tailwindcss').Config} */
export default {
  // No darkMode class toggle needed – we hardcode dark palette in CSS
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
