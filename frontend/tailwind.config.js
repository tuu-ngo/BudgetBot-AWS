
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './index.jsx',
    './pages/**/*.{js,jsx}',
    './components/**/*.{js,jsx}',
    './lib/**/*.{js}',
  ],
  theme: {
    extend: {
      colors: {
        cream: {
          DEFAULT: '#FAF6F0',
          50: '#FFFFFF',
          100: '#FDFBF9',
          200: '#FAF6F0',
          300: '#F4EBE0',
          400: '#EEDFD0',
          500: '#E8D3C0',
        },
        accent: {
          DEFAULT: '#F59E0B', // amber-500
          hover: '#D97706', // amber-600
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        serif: ['Instrument Serif', 'serif'],
      },
      boxShadow: {
        'soft': '0 10px 40px -10px rgba(0,0,0,0.05)',
        'card': '0 4px 20px -2px rgba(0,0,0,0.03)',
      }
    },
  },
  plugins: [],
}
