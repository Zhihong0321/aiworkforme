/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: 'rgb(var(--accent-rgb) / <alpha-value>)',
          foreground: 'rgb(var(--accent-foreground-rgb) / <alpha-value>)',
          strong: 'rgb(var(--accent-strong-rgb) / <alpha-value>)',
          soft: 'rgb(var(--accent-soft-rgb) / <alpha-value>)'
        },
        background: {
          light: 'rgb(var(--bg-rgb) / <alpha-value>)',
          dark: 'rgb(var(--bg-strong-rgb) / <alpha-value>)'
        },
        surface: {
          DEFAULT: 'rgb(var(--panel-rgb) / <alpha-value>)',
          elevated: 'rgb(var(--panel-elevated-rgb) / <alpha-value>)',
          muted: 'rgb(var(--panel-muted-rgb) / <alpha-value>)'
        },
        line: {
          DEFAULT: 'rgb(var(--border-rgb) / <alpha-value>)',
          strong: 'rgb(var(--border-strong-rgb) / <alpha-value>)'
        },
        ink: {
          DEFAULT: 'rgb(var(--text-rgb) / <alpha-value>)',
          muted: 'rgb(var(--muted-rgb) / <alpha-value>)',
          subtle: 'rgb(var(--muted-soft-rgb) / <alpha-value>)'
        },
        success: 'rgb(var(--success-rgb) / <alpha-value>)',
        warning: 'rgb(var(--warning-rgb) / <alpha-value>)',
        danger: 'rgb(var(--danger-rgb) / <alpha-value>)'
      },
      fontFamily: {
        display: ['Public Sans', 'Segoe UI', 'Tahoma', 'sans-serif'],
        mono: ['IBM Plex Mono', 'SFMono-Regular', 'Consolas', 'monospace']
      },
      boxShadow: {
        shell: '0 18px 42px -28px rgb(var(--text-rgb) / 0.42)',
        panel: '0 24px 48px -28px rgb(var(--text-rgb) / 0.28)'
      }
    },
  },
  plugins: [],
}
