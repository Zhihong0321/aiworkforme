import { ref } from 'vue'

const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('theme') : null
const theme = ref(stored === 'dark' ? 'dark' : 'light')

const applyTheme = (next) => {
  const value = next === 'dark' ? 'dark' : 'light'
  theme.value = value
  if (typeof document !== 'undefined') {
    document.documentElement.setAttribute('data-theme', value)
  }
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem('theme', value)
  }
}

// Apply immediately on module import
applyTheme(theme.value)

export const useTheme = () => {
  const setTheme = (value) => applyTheme(value)
  const toggleTheme = () => applyTheme(theme.value === 'dark' ? 'light' : 'dark')
  return { theme, setTheme, toggleTheme }
}
