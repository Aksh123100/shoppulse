/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brew & Co. palette — dark espresso + warm amber
        espresso: {
          50: '#fdf8f0',
          100: '#f7e8d0',
          200: '#edd4a3',
          300: '#e0b86e',
          400: '#d49a42',
          500: '#c47f2a',
          600: '#a86422',
          700: '#8a4e1f',
          800: '#6e3e1f',
          900: '#5a331c',
        },
        roast: {
          50: '#f5f0eb',
          100: '#e8d9cc',
          200: '#c9a98e',
          300: '#a87a56',
          400: '#8a5c3a',
          500: '#6e4226',
          600: '#59361f',
          700: '#452919',
          800: '#2e1c11',
          900: '#1a0f08',
        },
        cream: '#FEF9F3',
        gilt: '#D4A843',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['Playfair Display', 'Georgia', 'serif'],
      },
    },
  },
  plugins: [],
}
