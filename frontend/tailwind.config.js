/** @type {import('tailwindcss').Config} */
// Colours mirror the CSS variables in src/index.css so Tailwind classes and
// hand-written CSS stay on one palette.
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#1b6a45',
        'primary-dark': '#0f3527',
        'primary-light': '#e3efe8',
        sky: '#1b6a45',
        eco: '#1b6a45',
        warning: '#e0a32e',
        danger: '#b42318',
        neutral: {
          bg: '#f3f5f2',
          card: '#ffffff',
          border: '#dbe2dd',
          textMain: '#15201b',
          textMuted: '#5a6862'
        }
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        display: ['"Barlow Condensed"', '"Arial Narrow"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        xl: '14px',
        lg: '10px',
      },
    },
  },
  plugins: [],
}
