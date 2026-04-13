/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    screens: {
      xs: '475px',
      sm: '640px',
      md: '768px',
      lg: '1024px',
      xl: '1280px',
      '2xl': '1536px',
    },
    extend: {
      colors: {
        brand: {
          50: '#f5f6f7',
          100: '#e8eaed',
          200: '#d3d7dc',
          300: '#a8aeb8',
          400: '#86888a',
          500: '#6a6d70',
          600: '#515456',
          700: '#3a3c3e',
          800: '#32363a',
          900: '#1d2126',
          950: '#0f1114',
        },
        surface: {
          0: '#ffffff',
          50: '#f5f6f7',
          100: '#edeef0',
          200: '#e0e2e5',
          300: '#d3d7dc',
          400: '#b8bdc4',
        },
        shell: {
          DEFAULT: '#354a5f',
          light: '#3f5a73',
          dark: '#2b3d4f',
        },
        sap: {
          blue: '#0070f2',
          'blue-light': '#e8f0fe',
          'blue-hover': '#0058c4',
        },
        status: {
          ok: '#2d9d78',
          'ok-muted': '#e6f5ef',
          warn: '#e8a838',
          'warn-muted': '#fff8e5',
          critical: '#e5484d',
          'critical-muted': '#fff1f1',
          info: '#0070f2',
          'info-muted': '#e8f0fe',
        },
      },
      fontFamily: {
        sans: ['"Geist"', '"DM Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"Geist Mono"', '"JetBrains Mono"', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      boxShadow: {
        'card': '0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.03)',
        'card-hover': '0 2px 8px 0 rgb(0 0 0 / 0.06), 0 1px 3px 0 rgb(0 0 0 / 0.04)',
        'sidebar': '8px 0 30px 0 rgb(0 0 0 / 0.10)',
        'modal': '0 20px 60px -12px rgb(0 0 0 / 0.2), 0 8px 20px -8px rgb(0 0 0 / 0.1)',
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.35s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
